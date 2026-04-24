# Layer iv-c — synthetic DAX semantic probes

Each synthetic calc fixture ships an `<fixture>.expected_values.yaml`.
Runner loads generated TMDL via AS .NET load probe, evaluates
`(calc, filter_context)` tuples as DAX queries, compares within tolerance.
See spec §9 layer iv-c. Populated in Plan 3.
