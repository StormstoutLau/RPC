#!/bin/bash
# C 站硬件全量信息收集
set +e
echo "===== 1. SYSTEM (整机) ====="
sudo -n dmidecode -t system 2>/dev/null | grep -E 'Manufacturer|Product Name|Version|Serial|SKU|Family|UUID' | head -12
echo ""
echo "===== 2. BASEBOARD (主板) ====="
sudo -n dmidecode -t baseboard 2>/dev/null | grep -E 'Manufacturer|Product Name|Version|Serial|Asset' | head -10
echo ""
echo "===== 3. BIOS 信息 ====="
sudo -n dmidecode -t bios 2>/dev/null | grep -E 'Vendor|Version|Release Date|Address|ROM Size|Characteristics' | head -8
echo ""
echo "===== 4. CHASSIS ====="
sudo -n dmidecode -t chassis 2>/dev/null | grep -E 'Manufacturer|Type|Boot-up State' | head -5
echo ""
echo "===== 5. CPU ====="
lscpu 2>/dev/null | grep -E 'Model name|Vendor|CPU\(s\)|Socket|Stepping|Microcode|Model:' | head -8
echo ""
echo "===== 6. 内存 DIMM ====="
sudo -n dmidecode -t memory 2>/dev/null | grep -E 'Size:|Type:|Speed:|Manufacturer:|Part Number:|Locator:' | grep -v 'No Module' | head -12
echo ""
echo "===== 7. GPU PCI 详情 ====="
lspci -vvv -s c6:00.0 2>/dev/null | grep -E 'Subsystem|Region|LnkCap|LnkSta|Kernel driver|Kernel modules' | head -10
echo ""
echo "===== 8. 所有 PCI 设备 (ODM 线索) ====="
lspci 2>/dev/null | head -20