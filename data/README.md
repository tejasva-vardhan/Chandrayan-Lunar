# Demo Data Layout

This directory stores repository-side metadata for local lunar demo datasets.

Raw products are kept outside the repository. Set `CHANDRAYAN_DATA_ROOT` to the
folder that contains the local demo dataset. Do not commit raw PDS files into Git.

See [`manifests/demo_pairs.yaml`](manifests/demo_pairs.yaml) for the expected pair
structure and product IDs.

The initial EXP-000 pair is:

- OHRC: `ch2_ohr_ncp_20210402T0546284043_d_img_d18`
- LROC: `M150368601RC`
