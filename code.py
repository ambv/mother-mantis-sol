import winterbloom_sol as sol
from rplktrlib import RedBlue

import supervisor
supervisor.runtime.autoreload = False
reload = supervisor.reload
print(f"{supervisor.runtime.autoreload=}")

rb = RedBlue()
try:
    sol.run(rb.update)
except MemoryError:
    reload()
