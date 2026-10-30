# Legacy validation-only benchmark evidence

The runs directory contains the newest reproduction of the validation-only benchmark against the final runtime source.
30 seeds × 120 runs × 12 scenarios × 6 strategies = 259,200 trials. Compressed raw trial output for JIT-D guarded legacy
and naive replay contains 86,400 records. This method intentionally does not enforce strict AAIR independent proof.

The separate AAIR comparison is in ../aair/. Its 7 methods include the ordinary incremental data-dependency ablation
and independent-evidence gates. Do not attribute an evidence-source improvement to semantic slicing alone.
Both metadata files record the same final runtime code fingerprint. Agent tokens/costs are modelled; measured runtime,
correct outputs, silent errors and safe halts are reported with the synthetic-data boundary.
