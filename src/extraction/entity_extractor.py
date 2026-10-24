# -*- coding: utf-8 -*-
"""
Technical Entity and Relationship Extractor
Extracts technical identifiers, WMI classes, NT/Win32 APIs, Registry paths,
Drivers, Devices, IOCTLs, RVAs, Properties, and Relationships with strict provenance.
"""

import re
from typing import List, Dict, Any, Tuple
from ..parser.markdown_parser import MarkdownChunk, ParsedDocument

class ExtractedEntity:
    def __init__(
        self,
        canonical_name: str,
        name: str,
        entity_type: str,
        subsystem: str,
        description: str,
        aliases: List[str] = None,
        metadata: Dict[str, Any] = None
    ):
        self.canonical_name = canonical_name
        self.name = name
        self.entity_type = entity_type
        self.subsystem = subsystem
        self.description = description
        self.aliases = aliases or []
        self.metadata = metadata or {}

class ExtractedProperty:
    def __init__(
        self,
        entity_canonical: str,
        name: str,
        value: str = None,
        value_type: str = None,
        description: str = None,
        metadata: Dict[str, Any] = None
    ):
        self.entity_canonical = entity_canonical
        self.name = name
        self.value = value
        self.value_type = value_type
        self.description = description
        self.metadata = metadata or {}

class ExtractedMethod:
    def __init__(
        self,
        entity_canonical: str,
        name: str,
        language: str,
        implementation: str,
        description: str = None,
        metadata: Dict[str, Any] = None
    ):
        self.entity_canonical = entity_canonical
        self.name = name
        self.language = language
        self.implementation = implementation
        self.description = description
        self.metadata = metadata or {}

class ExtractedEvidence:
    def __init__(
        self,
        target_canonical: str,
        source_file: str,
        heading_path: List[str],
        start_line: int,
        source_text: str,
        confidence: float = 1.0,
        extraction_rule: str = ""
    ):
        self.target_canonical = target_canonical
        self.source_file = source_file
        self.heading_path = " -> ".join(heading_path) if heading_path else ""
        self.start_line = start_line
        self.source_text = source_text
        self.confidence = confidence
        self.extraction_rule = extraction_rule

class ExtractedRelationship:
    def __init__(
        self,
        source_canonical: str,
        relationship_type: str,
        target_canonical: str,
        confidence: float = 1.0,
        evidence: ExtractedEvidence = None
    ):
        self.source_canonical = source_canonical
        self.relationship_type = relationship_type
        self.target_canonical = target_canonical
        self.confidence = confidence
        self.evidence = evidence

class EntityExtractor:
    # Regex patterns
    WMI_CLASS_RE = re.compile(r'\b(Win32_[A-Za-z0-9_]+|Wmi[A-Za-z0-9_]+)\b')
    WMI_NS_RE = re.compile(r'\b(root\\[A-Za-z0-9_\\]+)\b', re.IGNORECASE)
    NT_API_RE = re.compile(r'\b(Nt[A-Z][A-Za-z0-9_]+|Zw[A-Z][A-Za-z0-9_]+|Rtl[A-Z][A-Za-z0-9_]+|Ob[A-Z][A-Za-z0-9_]+|Io[A-Z][A-Za-z0-9_]+)\b')
    WIN32_API_RE = re.compile(r'\b(DeviceIoControl|GetSystemFirmwareTable|GetAdaptersAddresses|CreateFile[AW]|GetProcAddress|Tbsip_[A-Za-z0-9_]+|Crypt[A-Za-z0-9_]+|QueryDisplayConfig)\b')
    IOCTL_HEX_RE = re.compile(r'\b(0x8[0-9a-fA-F]{7}|0x2[0-9a-fA-F]{6}|IOCTL_[A-Z0-9_]+|FSCTL_[A-Z0-9_]+)\b')
    REG_PATH_RE = re.compile(r'\b(HKLM\\[A-Za-z0-9_\\\-]+|SYSTEM\\CurrentControlSet\\[A-Za-z0-9_\\\-]+)\b', re.IGNORECASE)
    DRIVER_RE = re.compile(r'\b([A-Za-z0-9_\-]+\.sys)\b', re.IGNORECASE)
    DEVICE_RE = re.compile(r'(\\Device\\[A-Za-z0-9_\{\}\-]+)', re.IGNORECASE)
    RVA_RE = re.compile(r'\b(0x18[0-9a-fA-F]{7}|0x14[0-9a-fA-F]{7})\b')

    SMBIOS_TABLE_INFO = {
        0: ("BIOS Information", "Win32_BIOS", "Motherboard"),
        1: ("System Information", "Win32_ComputerSystemProduct", "System"),
        2: ("Baseboard Information", "Win32_BaseBoard", "Motherboard"),
        3: ("System Enclosure or Chassis", "Win32_SystemEnclosure", "System"),
        4: ("Processor Information", "Win32_Processor", "CPU"),
        7: ("Cache Information", "Win32_CacheMemory", "CPU"),
        8: ("Port Connector Information", "Win32_PortConnector", "Motherboard"),
        9: ("System Slots", "Win32_SystemSlot", "Motherboard"),
        11: ("OEM Strings", "Win32_ComputerSystem", "System"),
        16: ("Physical Memory Array", "Win32_PhysicalMemoryArray", "Memory"),
        17: ("Memory Device", "Win32_PhysicalMemory", "Memory"),
        19: ("Memory Array Mapped Address", "Win32_MemoryArray", "Memory"),
        32: ("System Boot Information", "Win32_SystemBootConfiguration", "System"),
        38: ("IPMI Device Information", None, "System"),
        41: ("Onboard Devices Extended Information", "Win32_PnPEntity", "Motherboard"),
        127: ("End-of-Table", None, "Firmware")
    }

    KNOWN_WMI_PROPS = {
        'WmiMonitorID': ['SerialNumberID', 'ManufacturerName', 'ProductCodeID', 'UserFriendlyName', 'WeekOfManufacture', 'YearOfManufacture'],
        'WmiMonitorBasicDisplayParams': ['MaxHorizontalImageSize', 'MaxVerticalImageSize', 'DisplayTransferCharacteristic'],
        'WmiMonitorConnectionParams': ['VideoOutputTechnology'],
        'Win32_BIOS': ['SMBIOSBIOSVersion', 'Manufacturer', 'SerialNumber', 'Version', 'ReleaseDate'],
        'Win32_BaseBoard': ['Manufacturer', 'Product', 'SerialNumber', 'Version'],
        'Win32_Processor': ['Name', 'Manufacturer', 'ProcessorId', 'NumberOfCores', 'NumberOfLogicalProcessors'],
        'Win32_VideoController': ['Caption', 'AdapterRAM', 'CurrentHorizontalResolution', 'CurrentVerticalResolution', 'DriverVersion', 'PNPDeviceID'],
        'Win32_DiskDrive': ['Caption', 'SerialNumber', 'Size', 'Model', 'PNPDeviceID', 'Signature'],
        'Win32_OperatingSystem': ['Caption', 'Version', 'OSArchitecture', 'CSDVersion', 'OSLanguage'],
        'Win32_NetworkAdapter': ['MACAddress', 'Name', 'AdapterType', 'Manufacturer', 'PNPDeviceID'],
        'Win32_PnPEntity': ['DeviceID', 'PNPDeviceID', 'Name', 'Manufacturer', 'HardwareID', 'ClassGuid']
    }

    @classmethod
    def extract_from_chunk(
        cls,
        doc: ParsedDocument,
        chunk: MarkdownChunk
    ) -> Tuple[List[ExtractedEntity], List[ExtractedProperty], List[ExtractedMethod], List[ExtractedRelationship], List[ExtractedEvidence]]:
        entities: Dict[str, ExtractedEntity] = {}
        properties: List[ExtractedProperty] = []
        methods: List[ExtractedMethod] = []
        relationships: List[ExtractedRelationship] = []
        evidences: List[ExtractedEvidence] = []

        text = chunk.content
        heading_path = chunk.heading_path

        def add_entity(canonical: str, name: str, etype: str, subsys: str, desc: str, aliases: List[str] = None):
            if canonical not in entities:
                entities[canonical] = ExtractedEntity(
                    canonical_name=canonical,
                    name=name,
                    entity_type=etype,
                    subsystem=subsys,
                    description=desc,
                    aliases=aliases or []
                )
            ev = ExtractedEvidence(
                target_canonical=canonical,
                source_file=doc.filename,
                heading_path=heading_path,
                start_line=chunk.start_line,
                source_text=text[:300] + ("..." if len(text) > 300 else ""),
                confidence=1.0,
                extraction_rule=f"regex_{etype}"
            )
            evidences.append(ev)
            return entities[canonical], ev

        # 1. WMI Classes
        for w_match in cls.WMI_CLASS_RE.finditer(text):
            w_class = w_match.group(1)
            canon = f"wmi.class.{w_class}"
            ent, ev = add_entity(canon, w_class, "wmi_class", "WMI", f"WMI Class {w_class}", aliases=[w_class.lower()])

            # Hardware Component category relationship
            hw_cat = cls._get_hardware_category_for_wmi(w_class)
            if hw_cat:
                hw_canon = f"hardware.{hw_cat.lower()}"
                add_entity(hw_canon, hw_cat, "hardware_component", "Hardware", f"Hardware Subsystem {hw_cat}")
                relationships.append(ExtractedRelationship(hw_canon, "CONTAINS", canon, 1.0, ev))

            # Namespace relationship
            ns = "root\\wmi" if w_class.startswith("Wmi") else "root\\cimv2"
            ns_canon = f"wmi.namespace.{ns.lower().replace(chr(92), '.')}"
            add_entity(ns_canon, ns, "wmi_namespace", "WMI", f"WMI Namespace {ns}")
            relationships.append(ExtractedRelationship(ns_canon, "CONTAINS", canon, 1.0, ev))

            # Method relationship (e.g. PowerShell)
            meth_canon = f"method.powershell.get_cim_{w_class.lower()}"
            meth = ExtractedMethod(canon, "Get-CimInstance", "PowerShell", f"Get-CimInstance -Namespace {ns} -ClassName {w_class}", f"PowerShell retrieval method for {w_class}")
            methods.append(meth)
            relationships.append(ExtractedRelationship(canon, "HAS_METHOD", meth_canon, 1.0, ev))

            # Known properties check in text
            known_props = cls.KNOWN_WMI_PROPS.get(w_class, [])
            for prop in known_props:
                if prop in text:
                    p_canon = f"property.{w_class.lower()}.{prop.lower()}"
                    prop_obj = ExtractedProperty(canon, prop, description=f"Property {prop} of WMI class {w_class}")
                    properties.append(prop_obj)
                    add_entity(p_canon, prop, "property", "WMI", f"Property {prop} of {w_class}")
                    relationships.append(ExtractedRelationship(canon, "HAS_PROPERTY", p_canon, 1.0, ev))

        # 2. NT Kernel APIs
        for nt_match in cls.NT_API_RE.finditer(text):
            api_name = nt_match.group(1)
            canon = f"api.ntdll.{api_name}"
            ent, ev = add_entity(canon, api_name, "api_function", "NTDLL", f"NT Kernel / Native API function {api_name}", aliases=[api_name.lower()])

        # 3. Win32 & Crypto & TBS APIs
        for w32_match in cls.WIN32_API_RE.finditer(text):
            api_name = w32_match.group(1)
            canon = f"api.win32.{api_name}"
            subsys = "TBS" if api_name.startswith("Tbsip") else ("CryptoAPI" if api_name.startswith("Crypt") else "Win32")
            ent, ev = add_entity(canon, api_name, "api_function", subsys, f"Win32 API {api_name}", aliases=[api_name.lower()])

        # 4. Drivers and Devices
        discovered_drivers = []
        for drv_match in cls.DRIVER_RE.finditer(text):
            drv_name = drv_match.group(1)
            canon = f"driver.{drv_name.lower().replace('.', '_')}"
            ent, ev = add_entity(canon, drv_name, "driver", "Drivers", f"System / Kernel driver {drv_name}")
            discovered_drivers.append((canon, ev))

        discovered_devices = []
        for dev_match in cls.DEVICE_RE.finditer(text):
            dev_name = dev_match.group(1)
            canon = f"device.{dev_name.lower().replace(chr(92), '.').replace('{', '').replace('}', '')}"
            ent, ev = add_entity(canon, dev_name, "device", "Device Object", f"Kernel Device Object {dev_name}")
            discovered_devices.append((canon, ev))

        # 5. IOCTL Codes
        for ioc_match in cls.IOCTL_HEX_RE.finditer(text):
            ioc_code = ioc_match.group(1)
            canon = f"ioctl.{ioc_code.lower()}"
            ent, ev = add_entity(canon, ioc_code, "ioctl", "Kernel IOCTL", f"IOCTL Control Code {ioc_code}")
            
            # Associate with discovered drivers/devices in the same chunk
            for drv_canon, drv_ev in discovered_drivers:
                relationships.append(ExtractedRelationship(drv_canon, "USES", canon, 0.9, ev))
            for dev_canon, dev_ev in discovered_devices:
                relationships.append(ExtractedRelationship(canon, "WRITES_TO", dev_canon, 0.9, ev))

        # 6. Registry Paths
        for reg_match in cls.REG_PATH_RE.finditer(text):
            reg_path = reg_match.group(1)
            canon = f"registry.{reg_path.lower().replace(chr(92), '.')}"
            ent, ev = add_entity(canon, reg_path, "registry_key", "Registry", f"Windows Registry Key {reg_path}")

        # 7. Reverse Engineering RVAs
        for rva_match in cls.RVA_RE.finditer(text):
            rva = rva_match.group(1)
            canon = f"rva.{rva.lower()}"
            ent, ev = add_entity(canon, rva, "rva_symbol", "Disassembly", f"Function RVA {rva}")

        # 8. SMBIOS Tables & Types
        is_smbios_context = (
            any(kw in h.lower() for h in heading_path for kw in ['smbios', 'dmi', 'firmware', 'rsmb'])
            or bool(re.search(r'\b(smbios|dmi|rsmb|getsystemfirmwaretable)\b', text, re.I))
        )

        if is_smbios_context:
            extracted_smbios_nums = set()

            # Pattern A: Lists like "Types 0 (BIOS), 1 (System UUID/SKU), 2 (Baseboard)..."
            list_matches = re.finditer(r'\bTypes?\s+((?:\d+\b(?:\s*\([^)]*\))?\s*(?:,\s*|and\s+)?)+)', text, re.I)
            for lm in list_matches:
                list_str = lm.group(1)
                for item in re.finditer(r'\b(\d+)\b(?:\s*\(([^)]+)\))?', list_str):
                    t_num = int(item.group(1))
                    if 0 <= t_num <= 255:
                        label = item.group(2).strip() if item.group(2) else None
                        extracted_smbios_nums.add((t_num, label))

            # Pattern B: Explicit "SMBIOS [table/structure] type N" or "SMBIOS Type N"
            for m in re.finditer(r'\bSMBIOS\s+(?:table\s+|structure\s+)?types?\s+(\d+)\b', text, re.I):
                t_num = int(m.group(1))
                if 0 <= t_num <= 255:
                    extracted_smbios_nums.add((t_num, None))

            # Pattern C: "Type N (Descriptive Label)" inside SMBIOS context
            for m in re.finditer(r'\bType\s+(\d+)\s*\(([^)]+)\)', text, re.I):
                t_num = int(m.group(1))
                if 0 <= t_num <= 255:
                    extracted_smbios_nums.add((t_num, m.group(2).strip()))

            for t_num, explicit_label in extracted_smbios_nums:
                canon = f"smbios.type_{t_num}"
                info = cls.SMBIOS_TABLE_INFO.get(t_num)
                standard_name = info[0] if info else (explicit_label or f"Type {t_num}")
                disp_name = f"SMBIOS Type {t_num} ({standard_name})" if standard_name else f"SMBIOS Type {t_num}"
                desc = f"SMBIOS Structure Table Type {t_num} ({standard_name})"
                
                aliases = [f"type {t_num}", f"type_{t_num}", f"smbios type {t_num}", f"smbios_type_{t_num}"]
                if explicit_label:
                    aliases.append(explicit_label.lower())
                
                ent, ev = add_entity(canon, disp_name, "smbios_type", "Firmware/SMBIOS", desc, aliases=aliases)

                if info:
                    wmi_cls = info[1]
                    hw_cat = info[2]
                    if wmi_cls:
                        wmi_canon = f"wmi.class.{wmi_cls}"
                        add_entity(wmi_canon, wmi_cls, "wmi_class", "WMI", f"WMI Class {wmi_cls}", aliases=[wmi_cls.lower()])
                        relationships.append(ExtractedRelationship(canon, "MAPS_TO_WMI", wmi_canon, 0.95, ev))
                    if hw_cat:
                        hw_canon = f"hardware.{hw_cat.lower()}"
                        add_entity(hw_canon, hw_cat, "hardware_component", "Hardware", f"Hardware Subsystem {hw_cat}")
                        relationships.append(ExtractedRelationship(hw_canon, "CONTAINS", canon, 0.9, ev))

        return list(entities.values()), properties, methods, relationships, evidences

    @staticmethod
    def _get_hardware_category_for_wmi(wmi_class: str) -> str:
        w_lower = wmi_class.lower()
        if 'monitor' in w_lower or 'display' in w_lower or 'video' in w_lower:
            return 'Monitor'
        elif 'disk' in w_lower or 'storage' in w_lower or 'volume' in w_lower:
            return 'Storage'
        elif 'processor' in w_lower or 'cpu' in w_lower:
            return 'CPU'
        elif 'baseboard' in w_lower or 'bios' in w_lower:
            return 'Motherboard'
        elif 'network' in w_lower or 'adapter' in w_lower:
            return 'Network'
        elif 'tpm' in w_lower:
            return 'TPM'
        elif 'pnp' in w_lower:
            return 'PnP Device'
        return 'System'
