#!/bin/bash
set -euo pipefail
bash "$(dirname "$0")/../_fixture/make-project.sh" --map
python3 - <<'PYFIX'
import json
from pathlib import Path
p=Path('docs/capabilities/map.json');d=json.loads(p.read_text())
d['servicePolicies']=[{'id':'delivery-review','kind':'assessment','revision':'1','basis':'Project delivery check','scope':'channel notification delivery','method':'manual delivery assessment','criteria':{'target':'Delivery meets all stated constraints.','unacceptable':'A delivery constraint fails.'},'maxAgeSeconds':300}]
d['rows'][0]['servicePolicyRefs']=['delivery-review'];p.write_text(json.dumps(d,indent=2)+'\n')
o={'row':'CAP-1','target':'delivery-review','revision':'1','scope':'channel notification delivery','method':'manual delivery assessment','assessor':'Synthetic fixture assessor','rationale':'Synthetic historical assessment, not real service evidence.','band':'target','observedAt':'2020-01-01T12:00:00Z','evidence':[{'ref':'synthetic/historical-review','description':'Clearly synthetic stale fixture.'}]}
Path('service-observations.json').write_text(json.dumps({'observations':[o]},indent=2)+'\n')
PYFIX
