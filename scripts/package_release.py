"""Explicit public allowlist; never includes credentials, sessions or old media."""
from pathlib import Path
import argparse,csv,io,json,re,zipfile
ROOT=Path(__file__).resolve().parents[1]

FILES=['README.md','docs/点点导购全流程.svg','docs/点点导购全流程与字段.md','docs/Agent决策接口与提示词.md','pyproject.toml','requirements.lock.txt','.env.example','.gitignore',
       'data/source/products.csv','data/source/perfume-verification.json','data/source/headphones.json','data/local-examples.json','data/curated-notes.json',
       'scripts/build_demo.py','scripts/demo-offline.mjs','scripts/build_local_examples.py','scripts/package_release.py',
       'scripts/evaluate_business.py','evaluations/business-v2.json','evaluations/business-v2-rubric.md',
       'tests/demo-static.test.mjs','tests/test_business_evaluation.py','tests/test_business_regressions.py','tests/test_agent_schema_repair.py',
       'tests/test_note_product_cards.py','tests/xhs-note-cards.test.mjs','tests/xhs-entry-controls.test.mjs','tests/test_semantic_authority.py','tests/test_generalization_output_guards.py','tests/test_general_preference_choices.py','tests/test_scope_generalization.py','tests/test_budget_scope_generalization.py','tests/test_product_first_flow.py','tests/test_product_scope.py','tests/test_explicit_preference_choices.py','tests/test_conditional_alternatives.py','tests/xhs-alternatives.test.mjs','tests/test_progressive_shopping.py','tests/test_typed_preference_facts.py','tests/test_clarification_fields.py','tests/test_curated_notes.py','tests/test_preference_followthrough.py','tests/test_multicategory.py','tests/test_portable_release.py','tests/xhs-multicategory.test.mjs',
       'docs/GitHub版本说明.md','docs/data/headphones-sources.md','docs/data/perfume-audit.md','docs/data/third-party-materials.md','docs/data/reader-notes-sources.md']
TREES=['demo','src/diandian','web/xhs','web/examples','.github/workflows']

def package(output):
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    paths={ROOT/name for name in FILES}
    for name in TREES:paths.update(p for p in (ROOT/name).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.pyo'))
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
        for path in sorted(paths):
            if not path.exists():raise ValueError('公开必需文件缺失：'+str(path.relative_to(ROOT)))
            name=path.relative_to(ROOT).as_posix();content=path.read_bytes()
            if name=='data/source/products.csv':
                # Only identity lookup from old source; validated facts come from overlays.
                records=list(csv.DictReader(io.StringIO(content.decode('utf-8-sig'))));out=io.StringIO();writer=csv.DictWriter(out,fieldnames=records[0].keys());writer.writeheader()
                for record in records:writer.writerow({k:v if k in ('product_id','product_name','brand','category','aliases') else '' for k,v in record.items()})
                content=out.getvalue().encode()
            if name=='web/xhs/app.js':
                # The public package uses independent local examples, no old prototype dependency.
                content=content.decode().replace("import {homeNotes as originalNotes} from '../reference/data.js';",'const originalNotes=[];').encode()
                content=content.decode().replace("notes=[fragrance[0],life[0],fragrance[1],life[1],fragrance[2],life[2],...fragrance.slice(3),...life.slice(3)];",'notes=fragrance;').encode()
            if name=='web/xhs/index.html':content=content.decode().replace('<a href="/web/index.html">打开工作流调试页 ↗</a>','').encode()
            if name.endswith('.css'):content=re.sub(rb'url\(["\']?\.\./reference/assets/[^)]+\)',b'none',content)
            z.writestr(name,content)
    return output

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='仅生成本地公开候选包，不上传GitHub')
    parser.add_argument('output',type=Path)
    print(package(parser.parse_args().output))
