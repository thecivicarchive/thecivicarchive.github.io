# Minnesota test files

`night/` holds the 2024 U.S. Senate count in three counties (Aitkin, Cook, Lake of the Woods: 82 precincts), written in
the layout of the Secretary of State's media results files by `python -m election.readers.mn_media --make-fixture`.

- The figures are official: the Secretary of State's 2024 general election results by precinct, published on the
  Minnesota Geospatial Commons (`us_mn_state_sos/bdry_electionresults_2022_2030`), read from the copy the kit already
  keeps in `states_cache/mn_local/sos_electionresults_2024.json` (fetched 2026-10-01, SHA-256
  dbb37327bcf4f615b8c3dc5a7b70b839193b5d3557e8497915592462fb5a4eab). Totals: White 8,371; Klobuchar 7,373;
  Whiting 222; Lacey 212; write-ins 13.
- The office ID (0102), the candidate order codes and the summary lines (county 88, standing in for the state with
  only these three counties) are the layout's, not the Secretary's own 2024 file.
- `precinct_table.txt` and `county_table.txt` follow the Secretary's reference tables; the congressional district and
  soil and water cells are left blank because the source does not carry them.
- No contact detail of any kind is in these files.
