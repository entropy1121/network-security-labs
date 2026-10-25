# SW2 ONLY: check for existing entries before applying; avoid duplicate ALLOW rules
/interface bridge port set [find where interface=ether4] learn=no
/interface bridge host add bridge=br-lab interface=ether4 mac-address=02:33:03:00:00:39
/interface bridge filter add chain=forward in-interface=ether4 src-mac-address=02:33:03:00:00:39/FF:FF:FF:FF:FF:FF action=accept comment=LAB03_ALLOW
/interface bridge filter add chain=forward in-interface=ether4 action=drop comment=LAB03_DROP_SPOOF
/interface bridge filter print stats
/interface bridge host print where on-interface=ether4
