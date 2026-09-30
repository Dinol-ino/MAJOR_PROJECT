import importlib.util
import os
import subprocess
import sys

import yaml

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "import_laws_of_india.py")
XML = """<akomaNtoso xmlns="http://www.akomantoso.org/2.0"><act><preface><p><shortTitle>Sample Act, 1999</shortTitle></p></preface>
<body><chapter><num>I</num><heading>Preliminary</heading>
<section id="section-1"><num>1.</num><heading>Short title.—</heading><paragraph><content><p>This Act may be called the Sample Act, 1999 and it applies to every contract entered into within India after commencement.</p></content></paragraph></section>
<section id="section-2"><num>2.</num><heading>Definitions.—</heading><paragraph><content><p>In this Act, unless the context otherwise requires, "agreement" means a promise or set of promises forming consideration.</p></content></paragraph></section>
</chapter></body></act></akomaNtoso>"""


def test_import_marks_everything_unverified_and_records_provenance(tmp_path):
    repo = tmp_path / "repo"; (repo / "consolidated").mkdir(parents=True)
    (repo / "consolidated" / "Sample Act, 1999.xml").write_text(XML, encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=a@b", "-c", "user.name=t", "commit", "-q",
                    "--allow-empty", "-m", "x"], check=True)
    out = tmp_path / "acts"
    subprocess.run([sys.executable, SCRIPT, str(repo), "--acts", "Sample", "--out", str(out)], check=True)
    txt = (out / "sample_act_1999.txt").read_text(encoding="utf-8")
    assert "Section 1. Short title" in txt and "Section 2. Definitions" in txt
    entry = yaml.safe_load((out / "manifest.yaml").read_text())["acts"]["sample_act_1999.txt"]
    assert entry["legal_status"] == "unverified" and "verified_at" not in entry
    assert "laws-of-india@" in entry["source_version"] and "NC-SA" in entry["source_version"]
    assert entry["year"] == 1999
