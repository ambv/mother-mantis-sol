import supervisor
supervisor.runtime.autoreload = False
print(f"{supervisor.runtime.autoreload=}")

import winterbloom_sol as sol
from rplktrlib import RedBlue


rb = RedBlue()
sol.run(rb.update)
