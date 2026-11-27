import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
"""Remove experimental attack bank, retain animation routes and known-good native sounds."""
import pathlib,struct,re,hashlib,shutil,json
H=pathlib.Path(__file__).resolve().parent; I=APP_ROOT/'installation'
base=H/'remaining-candidate/pre-install'; out=H/'ucb-recovery'; out.mkdir(exist_ok=True)
paths=['vilgax/ultimatecannonbolt/g_ucb.xbx','game/global/g_ucb.xbx','vilgax/ultimatecannonbolt/atk_ucb.ddf','game/global/scripts/atk_ucb.ddf','game/global/scripts/sounds.ddf','game/global/scripts/sndbnk.ddf','vilgax/ultimatecannonbolt/sounds.txt']
assert not (out/'pre-install').exists()
before={p:(I/p).read_bytes() for p in paths}; after={}
for p in paths[:2]:after[p]=(base/p).read_bytes()
assert after[paths[0]]==after[paths[1]]
for p in paths[2:4]:
    old=(base/p).read_bytes(); d=bytearray(before[p]); assert len(old)==len(d)==6500
    count=0
    for at in range(4,len(d),224):
        assert d[at:at+4]==old[at:at+4]
        if d[at+152:at+156]!=old[at+152:at+156]:
            d[at+152:at+156]=old[at+152:at+156];count+=1
    assert count==12
    after[p]=bytes(d)
assert after[paths[2]]==after[paths[3]]
s=before[paths[4]]; s,n=re.subn(rb'^<sound name="ucb_poe_(?:backspin|meteor|suction|spin)" id="\d+" swpgroupid="0" prjid="ucbpova"/>\r?\n',b'',s,flags=re.M);assert n==4;after[paths[4]]=s
s=before[paths[5]]; s,n=re.subn(rb'^\t<sfxbank file="ucbpova" [^\r\n]*\r?\n',b'',s,flags=re.M);assert n==1
s,n=re.subn(rb'^  <sfxeventgroups name="ucbpova">\r?\n\t<sfxeventgroup name="ucbpova"[^\r\n]*\r?\n  </sfxeventgroups>\r?\n',b'',s,flags=re.M);assert n==1;after[paths[5]]=s
assert all(b'ucbpova' not in after[p] for p in paths[4:6])
for p,data in before.items():
    f=out/'pre-install'/p;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(data)
for p,data in after.items():
    f=out/'prepared'/p;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(data)
    (I/p).write_bytes(data);assert (I/p).read_bytes()==data
# Keep the entire custom project available without letting the launcher register it.
(I/paths[6]).rename(out/'disabled-sounds.txt')
print('Restored original UCB package and 12 stock attack sound routes; removed only four experimental sound descriptors and their bank registration. Animation IDs unchanged.')
