"""Read-only AST/resource/i18n inventory; candidates require human review."""
import ast,hashlib,json,re
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def audit():
    files=sorted((ROOT/'app').rglob('*.py'));inventory=[];unused=[];large=[];duplicates=defaultdict(list);literal_keys=set();dynamic=set();exceptions=[]
    for file in files:
        source=file.read_text(encoding='utf-8-sig');tree=ast.parse(source);rel=file.relative_to(ROOT).as_posix()
        names={n.id for n in ast.walk(tree) if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Load)}
        for n in ast.walk(tree):
            if isinstance(n,(ast.Import,ast.ImportFrom)) and getattr(n,'module','')!='__future__' and file.name!='__init__.py':
                for alias in n.names:
                    name=alias.asname or alias.name.split('.')[0]
                    if name not in names:unused.append({'file':rel,'line':n.lineno,'name':name})
            if isinstance(n,ast.ClassDef) and rel.startswith('app/ui/'):
                inventory.append({'file':rel,'line':n.lineno,'class':n.name,'bases':[ast.unparse(b) for b in n.bases]})
            if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):
                length=n.end_lineno-n.lineno+1
                if length>150:large.append({'file':rel,'name':n.name,'lines':length})
                body=[b for b in n.body if not(isinstance(b,ast.Expr) and isinstance(b.value,ast.Constant) and isinstance(b.value.value,str))]
                if len(body)>1:
                    digest=hashlib.sha256(ast.dump(ast.Module(body=body,type_ignores=[]),include_attributes=False).encode()).hexdigest()
                    duplicates[digest].append(f'{rel}:{n.lineno} {n.name}')
            if isinstance(n,ast.ExceptHandler) and (n.type is None or ast.unparse(n.type)=='Exception'):
                exceptions.append({'file':rel,'line':n.lineno,'bare':n.type is None,'silent':all(isinstance(b,ast.Pass) for b in n.body)})
            if isinstance(n,ast.Call):
                func=ast.unparse(n.func)
                if rel.startswith('app/ui/') and any(word in func for word in ('QDialog','QMessageBox','QInputDialog','QFileDialog','QMenu(')):
                    inventory.append({'file':rel,'line':n.lineno,'factory':func})
                if func.endswith(('.tr','.tr_text')) or func=='tr':
                    if n.args and isinstance(n.args[0],ast.Constant) and isinstance(n.args[0].value,str):literal_keys.add(n.args[0].value)
                    elif n.args:dynamic.add(ast.unparse(n.args[0]))
    dictionaries={};repeat_definitions={}
    for code in ('zh_CN','en_US'):
        pairs=json.loads((ROOT/f'app/i18n/locales/{code}.json').read_text(encoding='utf-8'),object_pairs_hook=list)
        keys=[key for key,value in pairs];repeat_definitions[code]=[k for k in set(keys) if keys.count(k)>1];dictionaries[code]=dict(pairs)
    common=set(dictionaries['zh_CN'])&set(dictionaries['en_US']);equivalent=defaultdict(list)
    for k in sorted(common):equivalent[(dictionaries['zh_CN'][k],dictionaries['en_US'][k])].append(k)
    resources=defaultdict(list)
    for folder in ('assets','docs/ui_snapshots'):
        for file in (ROOT/folder).rglob('*'):
            if file.is_file():resources[hashlib.sha256(file.read_bytes()).hexdigest()].append(file.relative_to(ROOT).as_posix())
    qss=(ROOT/'app/themes/dark.qss').read_text(encoding='utf-8');rules=re.findall(r'([^{}]+)\{\{(.*?)\}\}',qss,re.S);same=defaultdict(list)
    for selector,body in rules:same[re.sub(r'\s+',' ',body.strip())].append(selector.strip())
    return {'python_files':len(files),'ui_inventory':inventory,'unused_import_candidates':unused,'large_functions':large,'exact_function_duplicates':[v for v in duplicates.values() if len(v)>1],
        'exception_boundaries':exceptions,'literal_i18n_missing':sorted(literal_keys-set(common)),
        'locale_key_mismatch':sorted(set(dictionaries['zh_CN'])^set(dictionaries['en_US'])),'duplicate_key_definitions':repeat_definitions,
        'dynamic_i18n_patterns':sorted(dynamic),'unreferenced_literal_candidates':sorted(common-literal_keys),
        'equivalent_i18n_groups':[v for v in equivalent.values() if len(v)>1],
        'resource_hash_duplicates':[v for v in resources.values() if len(v)>1],'qss_equal_declarations':[v for v in same.values() if len(v)>1]}

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='dev_data/hygiene-r3.json');args=parser.parse_args();result=audit();target=ROOT/args.output;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:len(result[k]) for k in ('ui_inventory','unused_import_candidates','exact_function_duplicates','literal_i18n_missing','resource_hash_duplicates')},ensure_ascii=False))
