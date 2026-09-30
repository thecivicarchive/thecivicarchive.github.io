"""One module per state: each reads that state's own official candidate list (and official primary results where
they are published as data) and returns rows for the candidates table. LOADERS names the states that have one."""

LOADERS = ("ca", "fl", "tx")
