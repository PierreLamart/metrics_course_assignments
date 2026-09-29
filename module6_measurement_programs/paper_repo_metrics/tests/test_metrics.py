"""Deterministic unit/integration tests. No third-party test runner is required."""
from __future__ import annotations
import copy
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from paper_repo_metrics.formulas import *
from paper_repo_metrics.graphs import CFG, Builder, UnsupportedControlFlow, graph_metrics, acyclic_path_count
from paper_repo_metrics.lexical import measure_lexical
from paper_repo_metrics.python_frontend import analyze_python
from paper_repo_metrics.java_frontend import analyze_java_batch, utf16_to_python_offsets
from paper_repo_metrics.smali_frontend import analyze_smali
from paper_repo_metrics.model import measure_model
from paper_repo_metrics.design import load_design, measure_design
from paper_repo_metrics.evaluation import (agreement, confusion_metrics, auc, classification,
    mean_average_precision, runtime_metrics, test_execution, evaluate, benchmark_inference)
from paper_repo_metrics.analyzer import analyze_repository, classify_apis, catalog
from paper_repo_metrics.repository import open_repository, RepositoryError, safe_relative
from paper_repo_metrics.cli import main, load_json, write_json, write_csvs

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / 'examples'


def python_method(code):
    m = analyze_python('module.py', code)['methods'][0]
    return graph_metrics(Builder().build(m['ir']))


def complete_python(code):
    parsed = analyze_python('module.py', code)
    for m in parsed['methods']:
        m['metrics'] = graph_metrics(Builder().build(m['ir']))
    linkage = measure_model(parsed['classes'], parsed['methods'])
    return parsed, linkage


class FormulaTests(unittest.TestCase):
    def test_p1_relative_example(self):
        r = relative_complexity([1]*7+[9])
        self.assertEqual(r['cc_mean'], 2)
        self.assertEqual(r['rci'], [.5]*7+[4.5])
        self.assertAlmostEqual(r['rcim'], 1+2*math.sqrt(1.75))
        self.assertEqual(r['rci_exceeds_rcim'], [False]*7+[True])
    def test_rci_average_one(self):
        self.assertAlmostEqual(relative_complexity([2,3,10])['rci_mean'], 1)
    def test_rci_empty_and_zero(self):
        self.assertIsNone(relative_complexity([])['rcim'])
        self.assertEqual(relative_complexity([0,0])['rci'], [None,None])
    def test_single_method_not_outlier(self):
        self.assertEqual(relative_complexity([99])['rci_exceeds_rcim'], [False])
    def test_invalid_k(self):
        with self.assertRaises(ValueError): relative_complexity([1], -1)
    def test_ic_base_ten(self):
        self.assertAlmostEqual(interaction_complexity(9,10,2),10.279953312878887)
    def test_ic_zero_connections(self):
        self.assertEqual(interaction_complexity(2,0,0), 2)
    def test_halstead(self):
        h=halstead({'+':3,'=':1},{'x':2,'y':2})
        self.assertEqual(h['halstead_length'],8)
        self.assertEqual(h['halstead_vocabulary'],4)
        self.assertEqual(h['halstead_volume'],16)
    def test_halstead_empty(self):
        self.assertEqual(halstead({}, {})['halstead_volume'],0)
    def test_halstead_negative_rejected(self):
        with self.assertRaises(ValueError): halstead({'+':-1},{})
    def test_lcom_printed_not_standard(self):
        self.assertEqual(lcom_p9_literal([['a','b'],['a','b']],['a','b']),-1)
    def test_lcom_undefined(self):
        self.assertIsNone(lcom_p9_literal([['a']],['a']))
        self.assertIsNone(lcom_p9_literal([[],[]],[]))
    def test_mi_coefficient_246(self):
        expected=171-5.2*math.log(20)-.23*3-16.2*math.log(10)+50*math.sin(math.sqrt(246*30))
        self.assertAlmostEqual(maintainability_p9_literal(20,3,10,30),expected)
    def test_mi_undefined(self):
        self.assertIsNone(maintainability_p9_literal(0,0,0,0))
    def test_rocr_example(self):
        self.assertAlmostEqual(rocr(73.7,66.1,77.9,47.9,5),2.511876)
    def test_rocr_zero_components(self):
        with self.assertRaises(ValueError): rocr(1,2,3,4,0)
    def test_software_health(self):
        self.assertEqual(software_health(60,75,90),75)
    def test_invalid_nonfinite_inputs(self):
        for value in (float('nan'),float('inf'),True):
            with self.subTest(value=value), self.assertRaises(ValueError): finite(value,'x')
    def test_ai_ratio(self):
        x=ai_ratio(['AI','Human','Unknown'])
        self.assertEqual(x['ai_ratio'],.5)
        self.assertEqual(x['unclassified_files'],1)
        self.assertIsNone(ai_ratio([])['ai_ratio'])
    def test_ai_bad_label(self):
        with self.assertRaises(ValueError): ai_ratio(['maybe'])
    def test_hybrid_arithmetic(self):
        self.assertEqual(raw_hybrid_complexity(6,4,2,log_base=2),6)
        self.assertEqual(new1([2,3],[4,6]),50)
        self.assertIsNone(new1([],[]))


class LexicalTests(unittest.TestCase):
    def test_python_comments_not_string(self):
        m,_,_=measure_lexical('# only\nx = "# string" # inline\n\n','python')
        self.assertEqual((m['total_lines'],m['loc'],m['comment_lines'],m['blank_lines']), (3,1,2,1))
        self.assertEqual(m['mixed_code_comment_lines'],1)
    def test_python_docstring_is_code(self):
        m,_,_=measure_lexical('"""module documentation"""\n','python')
        self.assertEqual(m['loc'],1)
        self.assertEqual(m['comment_lines'],0)
    def test_java_comment_inside_string(self):
        m,_,_=measure_lexical('String a = "http://x"; // c\n/* block\ncomment */\n','java')
        self.assertEqual(m['loc'],1)
        self.assertEqual(m['comment_lines'],3)
    def test_java_text_block(self):
        m,_,_=measure_lexical('String x = """\n// not comment\n""";\n','java')
        self.assertEqual(m['loc'],3)
        self.assertEqual(m['comment_lines'],0)
    def test_unicode_escape_refused(self):
        with self.assertRaises(ValueError): measure_lexical(r'\u002f\u002f comment','java')
    def test_smali_string_hash(self):
        m,_,_=measure_lexical('const-string v0, "# not comment" # yes\n','smali')
        self.assertEqual(m['loc'],1)
        self.assertEqual(m['comment_lines'],1)
        self.assertNotIn('halstead_volume',m)
    def test_java_binary_literal_single_operand(self):
        from paper_repo_metrics.lexical import java_lexemes
        ts=java_lexemes("0b1010L")
        self.assertEqual([(t.kind,t.text) for t in ts],[("operand","0b1010L")])
    def test_empty_file(self):
        m,_,_=measure_lexical('','python')
        self.assertEqual(m['total_lines'],0)
        self.assertIsNone(m['comment_percentage'])
    def test_no_final_newline(self):
        self.assertEqual(measure_lexical('x = 1','python')[0]['total_lines'],1)


class GraphTests(unittest.TestCase):
    def test_straight(self):
        self.assertEqual(python_method('def f():\n    return 1\n')['cc'],1)
    def test_if(self):
        m=python_method('def f(x):\n    if x:\n        return 1\n    return 0\n')
        self.assertEqual((m['cc'],m['npath_node_simple']),(2,2))
    def test_short_circuit_condition(self):
        m=python_method('def f(a,b):\n    if a and b:\n        return 1\n    return 0\n')
        self.assertEqual((m['cc'],m['npath_node_simple']),(3,3))
    def test_boolean_value(self):
        self.assertEqual(python_method('def f(a,b,c):\n    return a and b and c\n')['cc'],3)
    def test_ternary_value(self):
        self.assertEqual(python_method('def f(x):\n    return 1 if x else 2\n')['cc'],2)
    def test_not_value(self):
        self.assertEqual(python_method('def f(x):\n    return not x\n')['cc'],1)
    def test_chained_compare(self):
        self.assertEqual(python_method('def f(a,b,c):\n    if a < b < c:\n        return 1\n    return 2\n')['cc'],3)
    def test_loop_node_simple_convention(self):
        m=python_method('def f(x):\n    while x:\n        x -= 1\n    return x\n')
        self.assertEqual(m['cc'],2)
        self.assertEqual(m['npath_node_simple'],1)
    def test_early_unreachable_pruning(self):
        self.assertEqual(python_method('def f(x):\n    return 1\n    if x:\n        return 2\n')['cc'],1)
    def test_loop_break(self):
        self.assertEqual(python_method('def f(x):\n    while x:\n        if x > 1:\n            break\n        x -= 1\n    return x\n')['cc'],3)
    def test_unsupported_try(self):
        with self.assertRaises(UnsupportedControlFlow): python_method('def f():\n    try:\n        return 1\n    except Exception:\n        return 2\n')
    def test_unsupported_comprehension(self):
        with self.assertRaises(UnsupportedControlFlow): python_method('def f(xs):\n    return [x for x in xs]\n')
    def test_supplied_graph(self):
        x=json.loads((EXAMPLES/'cfg.json').read_text())
        m=graph_metrics(CFG.from_dict(x))
        self.assertEqual((m['cc'],m['npath_node_simple']),(2,2))
    def test_graph_invalid_edge(self):
        with self.assertRaises(ValueError): CFG.from_dict({'nodes':['a'],'entry':'a','edges':[['a','x']]})
    def test_path_step_limit_is_not_zero(self):
        g=CFG.from_dict({'nodes':['a','b','z'],'entry':'a','exits':['z'], 'edges':[['a','b'],['b','a'],['b','z']]})
        m=acyclic_path_count(g,max_steps=1)
        self.assertIsNone(m['value'])
        self.assertFalse(m['exact'])
    def test_graph_disconnected_components(self):
        g=CFG.from_dict({'nodes':['a','z','b','c'],'entry':'a','exits':['z'], 'edges':[['a','z'],['b','c']]})
        self.assertEqual(graph_metrics(g)['cfg_components'],2)


class EvaluationTests(unittest.TestCase):
    def test_confusion(self):
        m=confusion_metrics(2,1,1,0)
        self.assertEqual(m['accuracy'],.75)
        self.assertEqual(m['recall'],1)
        self.assertEqual(m['f1'],.8)
        self.assertAlmostEqual(m['mcc'],1/math.sqrt(3))
    def test_zero_denominators(self):
        m=confusion_metrics(0,0,0,0)
        for k in ('accuracy','precision','recall','f1','mcc'): self.assertIsNone(m[k])
    def test_auc_paper_ties(self):
        self.assertEqual(auc([0,1],[.5,.5]),0)
        self.assertEqual(auc([0,1],[.5,.5],tie_credit=.5),.5)
    def test_auc_perfect(self):
        self.assertEqual(auc([0,0,1,1],[.1,.2,.8,.9]),1)
    def test_auc_single_class(self):
        self.assertIsNone(auc([1,1],[.2,.3]))
    def test_rmse_probabilities(self):
        x=classification({'y_true':[0,1],'probabilities':[.2,.8]})
        self.assertAlmostEqual(x['binary']['rmse'],.2)
    def test_kappa_multiclass(self):
        x=agreement(['a','b','c'],['a','b','c'])
        self.assertEqual(x['cohens_kappa'],1)
        self.assertEqual(x['percentage_agreement'],100)
    def test_kappa_constant_undefined(self):
        self.assertIsNone(agreement([1,1],[1,1])['cohens_kappa'])
    def test_multiclass(self):
        x=classification({'y_true':['a','b','c'],'y_pred':['a','b','b']})
        self.assertEqual(len(x['per_class']),3)
        self.assertNotIn('binary',x)
    def test_invalid_lengths(self):
        with self.assertRaises(ValueError): classification({'y_true':[0,1],'y_pred':[1]})
    def test_map_complete(self):
        data={f'{.5+.05*i:.2f}':{'c':.8,'d':.6} for i in range(10)}
        x=mean_average_precision(data)
        self.assertAlmostEqual(x['map_50_95'],.7)
    def test_map_incomplete_is_null(self):
        self.assertIsNone(mean_average_precision({'0.50':{'c':.8}})['map_50_95'])
    def test_map_different_classes(self):
        data={f'{.5+.05*i:.2f}':{'c':.8} for i in range(10)}
        data['0.95']={'d':.8}
        self.assertIsNone(mean_average_precision(data)['map_50_95'])
    def test_weighted_latency(self):
        x=runtime_metrics([{'images':1,'elapsed_ms':10},{'images':9,'elapsed_ms':90}])
        self.assertEqual(x['latency_ms_per_image'],10)
        self.assertIsNone(x['gpu_memory_mb_max_observed'])
    def test_gpu_supplied(self):
        x=runtime_metrics([{'images':1,'elapsed_ms':10,'gpu_memory_mb':12}])
        self.assertEqual(x['gpu_memory_mb_max_observed'],12)
    def test_test_prefix(self):
        x=test_execution({'tests':[{'id':'a','duration_ms':2,'faults':['F']},{'id':'b','duration_ms':3,'faults':[]}]})
        self.assertEqual(x['suite_percentage_to_cover_all_faults'],50)
        self.assertEqual(x['time_to_cover_all_faults_ms'],2)
        self.assertEqual(x['test_execution_time_ms'],5)
    def test_uncovered_known_fault(self):
        x=test_execution({'fault_universe':['F'],'tests':[{'id':'a','duration_ms':1,'faults':[]}]})
        self.assertIsNone(x['suite_percentage_to_cover_all_faults'])
        self.assertEqual(x['uncovered_faults'],['F'])
    def test_no_faults(self):
        self.assertIsNone(test_execution({'tests':[]})['suite_percentage_to_cover_all_faults'])
    def test_auxiliary_example(self):
        x=evaluate(json.loads((EXAMPLES/'auxiliary.json').read_text()))
        self.assertEqual(x['citations']['citation_count'],2)
        self.assertEqual(x['hybrid']['new1'],50)
    def test_string_binary_positive_label_required(self):
        with self.assertRaises(ValueError): classification({"y_true":["a","b"],"y_pred":["a","b"]})
    def test_unknown_section_rejected(self):
        with self.assertRaises(ValueError): evaluate({'typo':[]})
    def test_opt_in_benchmark(self):
        calls=[]
        x=benchmark_inference(lambda:calls.append(1),iterations=3,warmup=2)
        self.assertEqual(len(calls),5)
        self.assertEqual(x['metrics']['images'],3)
        self.assertIsNone(x['metrics']['gpu_memory_mb_mean'])


class ModelTests(unittest.TestCase):
    def test_all_24_design_keys(self):
        x=load_design(EXAMPLES/'design_model.json')
        self.assertEqual(len(x['classes'][-1]['metrics']),24)
    def test_design_known_values(self):
        x=load_design(EXAMPLES/'design_model.json')
        a=next(c['metrics'] for c in x['classes'] if c['id']=='A')
        self.assertEqual(a['dit'],1)
        self.assertEqual(a['method_count'],2)
        self.assertEqual(a['getters'],1)
        self.assertEqual(a['setters'],1)
        self.assertEqual(a['inherited_operations_known'],1)
        self.assertEqual(a['ic_attr_known'],1)
        self.assertEqual(a['ic_par_known'],1)
        self.assertEqual(a['assoc'],1)
    def test_xmi_json_equivalent(self):
        a=load_design(EXAMPLES/'design_model.json')
        b=load_design(EXAMPLES/'design_model.xmi','prefix_comparable')
        self.assertEqual({c['id']:c['metrics'] for c in a['classes']},{c['id']:c['metrics'] for c in b['classes']})
    def test_no_inferred_associations(self):
        data=json.loads((EXAMPLES/'design_model.json').read_text()); data.pop('associations')
        x=measure_design(data)
        self.assertIsNone(x['classes'][-1]['metrics']['assoc'])
    def test_scope_policy_required(self):
        data=json.loads((EXAMPLES/'design_model.json').read_text());data.pop('scope_branch_policy')
        x=measure_design(data)['classes'][-1]['metrics']
        self.assertIsNone(x['num_ass_el_sb'])
        self.assertEqual(x['num_ass_el_ssc'],1)
    def test_cycle_null(self):
        x=measure_design({'classes':[{'id':'A','parents':['B']},{'id':'B','parents':['A']}]})
        self.assertIsNone(x['classes'][0]['metrics']['dit'])
        self.assertTrue(x['classes'][0]['linkage']['hierarchy_cycle_or_dependency_on_cycle'])
    def test_missing_ancestor_null(self):
        x=measure_design({'classes':[{'id':'A','parents':['External']} ]})
        self.assertIsNone(x['classes'][0]['metrics']['dit'])
    def test_diamond_ancestors_deduplicated(self):
        x=measure_design({'classes':[{'id':'A'},{'id':'B','parents':['A']},{'id':'C','parents':['A']},{'id':'D','parents':['B','C']}]})
        self.assertEqual(x['classes'][-1]['metrics']['num_ancestors_known'],3)
        self.assertEqual(x['classes'][-1]['metrics']['dit'],2)
    def test_python_self_call(self):
        parsed,link=complete_python('class A:\n    def get(self):\n        return 1\n    def f(self):\n        return self.get()\n')
        self.assertEqual(len(link['resolved_edges']),1)
        self.assertEqual(parsed['methods'][0]['metrics']['fanin_resolved'],1)
    def test_python_dynamic_call_unresolved(self):
        parsed,link=complete_python('def f(x):\n    return x.run()\n')
        self.assertEqual(len(link['unresolved_calls']),1)
        self.assertEqual(parsed['methods'][0]['metrics']['fanout_resolved'],0)
    def test_python_visibility_not_invented(self):
        p,l=complete_python('class A:\n    def _f(self):\n        return 1\n')
        self.assertIsNone(p['classes'][0]['metrics']['private_methods'])
    def test_nested_function_not_class_method(self):
        p,l=complete_python('class A:\n    def f(self):\n        def inner():\n            return 1\n        return inner()\n')
        self.assertEqual(p['classes'][0]['metrics']['method_count'],1)
        self.assertEqual(len(p['methods']),2)
    def test_syntactic_getters(self):
        p,l=complete_python('class A:\n    def island(self):\n        return 1\n')
        self.assertEqual(p['classes'][0]['metrics']['getters'],1)
    def test_duplicate_ids_rejected(self):
        with self.assertRaises(ValueError): measure_design({'classes':[{'id':'A'},{'id':'A'}]})
    def test_api_missing_not_zero(self):
        self.assertIsNone(classify_apis([],None)['counts']['network_op'])
    def test_api_registry_only(self):
        sites=[{'api_target':'Lx;->send()V'},{'api_target':'Lx;->send()V'}]
        x=classify_apis(sites,{'network_op':['Lx;->send*']})
        self.assertEqual(x['counts']['network_op'],2)
        self.assertIsNone(x['counts']['sqlite_op'])


@unittest.skipUnless(shutil.which('java') and shutil.which('javac'), 'JDK not installed')
class JavaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results,cls.version=analyze_java_batch({
          'good.java':'''package demo;
interface I { int get(); }
class A {
  private int value;
  static { int x=1; x++; }
  public int get() { return value; }
  void set(int value) { this.value=value; }
  int shadow(int value) { return value; }
  void variadic(String... xs) { }
  void call() { variadic("a", "b"); }
  int pick(int n) { switch(n) { case 1: return 1; case 2: return 2; default:return 0; } }
  int guarded() { try { return 1; } catch(Exception e) { return 2; } }
}
''',
          'broken.java':'class Broken { void f( { }',
          'utf.java':'class Utf { String s="\U0001f600"; int f(){ return 2; } }',
          'local.java':'class Outer { void f(){ class Inner { int g(){return 1;} } } }',
          'overloaded.java':'class O { void x(int a){} void x(String a){} void f(){ x(1); } }',
        })
    def test_parse_errors(self):
        self.assertFalse(self.results['broken.java']['parse_ok'])
        self.assertTrue(self.results['good.java']['parse_ok'])
    def test_java_fields_and_visibility(self):
        p=copy.deepcopy(self.results['good.java'])
        measure_model(p['classes'],p['methods'])
        a=next(c for c in p['classes'] if c['name']=='A')
        self.assertEqual(a['metrics']['instance_variables'],1)
        self.assertEqual(a['metrics']['public_methods'],1)
        self.assertEqual(a['metrics']['default_methods'],6)
    def test_parameter_shadowing(self):
        p=self.results['good.java']
        s=next(m for m in p['methods'] if m['name']=='shadow')
        self.assertEqual(s['field_accesses'],[])
        s=next(m for m in p['methods'] if m['name']=='set')
        self.assertEqual(s['field_accesses'],['value'])
    def test_varargs_call(self):
        p=copy.deepcopy(self.results['good.java'])
        linkage=measure_model(p['classes'],p['methods'])
        f=next(m for m in p['methods'] if m['name']=='call')
        self.assertEqual(f['metrics']['fanout_resolved'],1)
    def test_switch_cc(self):
        m=next(m for m in self.results['good.java']['methods'] if m['name']=='pick')
        self.assertEqual(graph_metrics(Builder().build(m['ir']))['cc'],3)
    def test_java_try_not_fabricated(self):
        m=next(m for m in self.results['good.java']['methods'] if m['name']=='guarded')
        with self.assertRaises(UnsupportedControlFlow): Builder().build(m['ir'])
    def test_utf16_offsets(self):
        self.assertEqual(utf16_to_python_offsets('a\U0001f600b'),[0,1,1,2,3])
        self.assertTrue(self.results['utf.java']['parse_ok'])
    def test_local_class_not_double_counted(self):
        p=self.results['local.java']
        self.assertEqual(p['metrics']['declarative_statements'],4)
        self.assertEqual(p['metrics']['executable_statements'],1)
    def test_initializer_statements_counted(self):
        self.assertGreater(self.results['good.java']['metrics']['executable_statements'],0)
    def test_overloads_not_guessed(self):
        p=copy.deepcopy(self.results['overloaded.java'])
        l=measure_model(p['classes'],p['methods'])
        self.assertEqual(len(l['unresolved_calls']),1)


class SmaliTests(unittest.TestCase):
    def test_bytecode_count(self):
        p=analyze_smali('Example.smali',(EXAMPLES/'demo_repo/Example.smali').read_text())
        self.assertTrue(p['parse_ok'])
        self.assertEqual(p['metrics']['bytecode_instructions'],7)
    def test_smali_branch_cc(self):
        p=analyze_smali('Example.smali',(EXAMPLES/'demo_repo/Example.smali').read_text())
        m=next(m for m in p['methods'] if m['name']=='ping')
        self.assertEqual(graph_metrics(CFG.from_dict(m['supplied_cfg']))['cc'],2)
    def test_smali_exact_external_signature(self):
        p=analyze_smali('Example.smali',(EXAMPLES/'demo_repo/Example.smali').read_text())
        l=measure_model(p['classes'],p['methods'])
        self.assertEqual(len(l['resolved_edges']),2)
        self.assertEqual(len(l['unresolved_calls']),0)


@unittest.skipUnless(shutil.which('git'), 'Git not installed')
class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.repo=Path(self.tmp.name)/'repo';self.repo.mkdir()
        self.command('init','-q')
        self.command('config','user.name','Metrics Tests')
        self.command('config','user.email','metrics@example.invalid')
        (self.repo/'a.py').write_text('def f(x):\n    if x:\n        return 1\n    return 0\n')
        (self.repo/'.gitignore').write_text('ignored.py\n')
        self.command('add','.');self.command('commit','-q','-m','fixture')
    def tearDown(self):self.tmp.cleanup()
    def command(self,*args):
        return subprocess.run(['git','-C',str(self.repo),*args],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).stdout.decode().strip()
    def test_working_tree(self):
        r=analyze_repository(str(self.repo))
        self.assertEqual(r['project']['sum_cyclomatic'],2)
        self.assertTrue(r['coverage']['full_structural_coverage_of_selected_files'])
    def test_tracked_only(self):
        (self.repo/'new.py').write_text('pass\n')
        self.assertEqual(analyze_repository(str(self.repo))['project']['file_count'],1)
    def test_include_untracked_respects_ignore(self):
        (self.repo/'new.py').write_text('pass\n');(self.repo/'ignored.py').write_text('pass\n')
        self.assertEqual(analyze_repository(str(self.repo),include_untracked=True)['project']['file_count'],2)
    def test_ref_does_not_modify_dirty_tree(self):
        (self.repo/'a.py').write_text('def f():\n    return 1\n')
        r=analyze_repository(str(self.repo),ref='HEAD')
        self.assertEqual(r['project']['sum_cyclomatic'],2)
        self.assertIn('def f():',(self.repo/'a.py').read_text())
    def test_unsupported_language_is_visible(self):
        (self.repo/'other.go').write_text('package main\n');self.command('add','other.go')
        r=analyze_repository(str(self.repo))
        self.assertEqual(r['coverage']['skipped_reason_counts']['unsupported_language'],1)
        self.assertFalse(r['coverage']['full_structural_coverage_of_selected_files'])
    def test_parse_error_not_zero(self):
        (self.repo/'bad.py').write_text('def f(:\n');self.command('add','bad.py')
        r=analyze_repository(str(self.repo))
        self.assertEqual(r['coverage']['structurally_measured_files'],1)
    def test_file_size_limit(self):
        r=analyze_repository(str(self.repo),max_file_bytes=1)
        self.assertEqual(r['coverage']['skipped_reason_counts']['file_size_limit'],1)
    def test_symlink_not_followed(self):
        try:(self.repo/'link.py').symlink_to('a.py')
        except OSError:self.skipTest('symlink unsupported')
        self.command('add','link.py')
        r=analyze_repository(str(self.repo))
        self.assertEqual(r['coverage']['skipped_reason_counts']['symlink'],1)
    def test_no_target_execution(self):
        (self.repo/'evil.py').write_text('from pathlib import Path\nPath("SHOULD_NOT_EXIST").write_text("bad")\n')
        self.command('add','evil.py');analyze_repository(str(self.repo))
        self.assertFalse((self.repo/'SHOULD_NOT_EXIST').exists())
        self.assertFalse((ROOT/'SHOULD_NOT_EXIST').exists())
    def test_cfg_override(self):
        r=analyze_repository(str(self.repo));mid=r['methods'][0]['id']
        simple={'nodes':['a','z'],'entry':'a','exits':['z'],'edges':[['a','z']]}
        r=analyze_repository(str(self.repo),cfg_overrides={mid:simple})
        self.assertEqual(r['methods'][0]['metrics']['cc'],1)
        self.assertEqual(r['methods'][0]['cfg_origin'],'user_supplied')
    def test_partial_cc_lower_bound(self):
        (self.repo/'a.py').write_text('def f():\n    return 1\ndef g():\n    try:\n        return 1\n    except:\n        return 2\n')
        r=analyze_repository(str(self.repo))
        self.assertIsNone(r['project']['sum_cyclomatic'])
        self.assertEqual(r['project']['sum_cyclomatic_measured_lower_bound'],1)
    def test_cli_report(self):
        path=Path(self.tmp.name)/'r.json'
        self.assertEqual(main(['scan',str(self.repo),'-o',str(path)]),0)
        self.assertTrue(json.loads(path.read_text())['methods'])
    def test_cli_incomplete_exit(self):
        (self.repo/'bad.py').write_text('def f(:');self.command('add','bad.py')
        self.assertEqual(main(['scan',str(self.repo),'-o',str(Path(self.tmp.name)/'r.json'),'--fail-on-incomplete']),2)
    def test_space_in_source_path(self):
        (self.repo/"space name.py").write_text("def g():\n    return 1\n")
        self.command("add","space name.py")
        r=analyze_repository(str(self.repo))
        self.assertEqual(r["project"]["file_count"],2)
    def test_git_fsmonitor_is_not_executed(self):
        hook=self.repo/"monitor.sh"
        hook.write_text("#!/bin/sh\ntouch FS_MONITOR_EXECUTED\n")
        hook.chmod(0o755)
        self.command("config","core.fsmonitor",str(hook))
        analyze_repository(str(self.repo))
        self.assertFalse((self.repo/"FS_MONITOR_EXECUTED").exists())
    def test_local_bare_repo(self):
        bare=Path(self.tmp.name)/'bare.git'
        subprocess.run(['git','clone','--bare','-q',str(self.repo),str(bare)],check=True)
        r=analyze_repository(str(bare))
        self.assertEqual(r['repository']['measurement_source'],'git_blobs')
    def test_invalid_ref_and_untracked(self):
        with self.assertRaises(RepositoryError):
            with open_repository(str(self.repo),ref='HEAD',include_untracked=True):pass


class InputOutputTests(unittest.TestCase):
    def test_json_nonfinite_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'x.json';p.write_text('{"x":NaN}')
            with self.assertRaises(ValueError):load_json(p)
    def test_csv_formula_escaping(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_csvs({'files':[{'path':'=bad.py','metrics':{'loc':1}}]},Path(tmp))
            self.assertIn("'=bad.py",(Path(tmp)/'files.csv').read_text())
    def test_atomic_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'out/r.json';write_json({'a':None},p)
            self.assertEqual(json.loads(p.read_text()),{'a':None})
            self.assertEqual(list(p.parent.glob('*.tmp')),[])
    def test_safe_relative(self):
        with self.assertRaises(RepositoryError):safe_relative('../escape.py')
    def test_catalog_has_unique_ids(self):
        c=catalog()['metrics'];self.assertEqual(len(c),len({x['id'] for x in c}))
    def test_xmi_rejects_entities(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'bad.xmi';p.write_text('<!DOCTYPE x [<!ENTITY y "z">]><x/>')
            with self.assertRaises(ValueError):load_design(p)


if __name__=='__main__':unittest.main()
