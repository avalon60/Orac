

# Now import orac
from  controller import orac


import conn_mgr
print(f"Orac module path: {orac.__file__}")
orac.hello()