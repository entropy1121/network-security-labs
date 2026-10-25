# SW1-CHR; first check no existing bridge/ports
/system identity set name=LAB03-SW1
/interface bridge add name=br-lab protocol-mode=rstp
/interface bridge port add bridge=br-lab interface=ether1
/interface bridge port add bridge=br-lab interface=ether2
/interface bridge port add bridge=br-lab interface=ether3
/interface bridge port print
