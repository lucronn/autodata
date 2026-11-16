"""Public-only reserve accounting; no runtime operations."""
ABSOLUTE=5368709120
DRIFT=134217728
PREP=134217728
INSTALL=67108864
EXTERNAL_STOP=100663296
ENTRY=ABSOLUTE+DRIFT+PREP+INSTALL

def budget(free,inodes,prep,install,baseline_free,baseline_owned):
    if inodes<=1000:raise RuntimeError('home_inode_floor')
    if not 0<=prep<=PREP:raise RuntimeError('prep_cap')
    if not 0<=install<=INSTALL:raise RuntimeError('install_cap')
    owned=prep+install
    floor=ABSOLUTE+DRIFT+(PREP-prep)+(INSTALL-install)
    if free<=floor:raise RuntimeError('home_capacity_floor')
    external=max(0,baseline_free-free-(owned-baseline_owned))
    if external>=EXTERNAL_STOP:raise RuntimeError('external_growth_stop')
    return {'required_free_exclusive':floor,'external_growth':external,'prep':prep,'install':install}
