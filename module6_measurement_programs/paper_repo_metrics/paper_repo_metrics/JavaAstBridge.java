/* Parser bridge only. Requires JDK 17+. All metric calculations are in Python.
 * Calls JavacTask.parse(), never analyze(), generate(), or target code.
 * Input: UTF-8 manifest of base64(relative path) TAB base64(absolute path).
 * Output: one JSON object per compilation unit.
 */
import com.sun.source.tree.*;
import com.sun.source.util.*;
import javax.tools.*;
import javax.lang.model.element.Modifier;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

public class JavaAstBridge {
    static Map<String,Object> obj(Object... pairs) {
        Map<String,Object> out = new LinkedHashMap<>();
        for (int i=0; i<pairs.length; i+=2) out.put((String)pairs[i], pairs[i+1]);
        return out;
    }
    static String str(Object x) { return x == null ? "" : x.toString(); }
    static String json(Object x) {
        if (x == null) return "null";
        if (x instanceof Number || x instanceof Boolean) return x.toString();
        if (x instanceof Map<?,?> m) {
            List<String> p = new ArrayList<>();
            for (var e : m.entrySet()) p.add(json(e.getKey().toString())+":"+json(e.getValue()));
            return "{"+String.join(",",p)+"}";
        }
        if (x instanceof Iterable<?> values) {
            List<String> p = new ArrayList<>();
            for (Object value: values) p.add(json(value));
            return "["+String.join(",",p)+"]";
        }
        StringBuilder b = new StringBuilder("\"");
        for (char c: x.toString().toCharArray()) {
            switch(c) {
                case '"': b.append("\\\""); break;
                case '\\': b.append("\\\\"); break;
                case '\n': b.append("\\n"); break;
                case '\r': b.append("\\r"); break;
                case '\t': b.append("\\t"); break;
                default: if(c < 32) b.append(String.format("\\u%04x",(int)c)); else b.append(c);
            }
        }
        return b.append('"').toString();
    }
    static Map<String,Object> ordinary(Object... children) {
        List<Object> cs = new ArrayList<>();
        for(Object x: children) if(x != null) cs.add(x);
        return obj("kind","ordinary","children",cs);
    }
    static Map<String,Object> expr(ExpressionTree e) {
        if(e == null) return ordinary();
        if(e instanceof ParenthesizedTree t) return expr(t.getExpression());
        if(e instanceof BinaryTree t) {
            String k = e.getKind()==Tree.Kind.CONDITIONAL_AND ? "and" :
                       e.getKind()==Tree.Kind.CONDITIONAL_OR ? "or" : "ordinary";
            return obj("kind",k,"children",List.of(expr(t.getLeftOperand()),expr(t.getRightOperand())));
        }
        if(e instanceof UnaryTree t) return obj("kind", e.getKind()==Tree.Kind.LOGICAL_COMPLEMENT ? "not":"ordinary",
                                               "children",List.of(expr(t.getExpression())));
        if(e instanceof ConditionalExpressionTree t) return obj("kind","ternary","test",expr(t.getCondition()),
                                               "then",expr(t.getTrueExpression()),"else",expr(t.getFalseExpression()));
        if(e instanceof AssignmentTree t) return ordinary(expr(t.getVariable()),expr(t.getExpression()));
        if(e instanceof CompoundAssignmentTree t) return ordinary(expr(t.getVariable()),expr(t.getExpression()));
        if(e instanceof TypeCastTree t) return ordinary(expr(t.getExpression()));
        if(e instanceof InstanceOfTree t) return ordinary(expr(t.getExpression()));
        if(e instanceof ArrayAccessTree t) return ordinary(expr(t.getExpression()),expr(t.getIndex()));
        if(e instanceof MemberSelectTree t) return ordinary(expr(t.getExpression()));
        if(e instanceof MethodInvocationTree t) {
            List<Object> cs = new ArrayList<>(); cs.add(expr(t.getMethodSelect()));
            for(var a: t.getArguments()) cs.add(expr(a));
            return obj("kind","ordinary","children",cs);
        }
        if(e instanceof NewClassTree t) {
            List<Object> cs = new ArrayList<>(); cs.add(expr(t.getEnclosingExpression()));
            for(var a:t.getArguments()) cs.add(expr(a));
            return obj("kind","ordinary","children",cs);
        }
        if(e instanceof NewArrayTree t) {
            List<Object> cs = new ArrayList<>();
            for(var a:t.getDimensions()) cs.add(expr(a));
            if(t.getInitializers()!=null) for(var a:t.getInitializers()) cs.add(expr(a));
            return obj("kind","ordinary","children",cs);
        }
        if(e instanceof LambdaExpressionTree || e instanceof IdentifierTree || e instanceof LiteralTree) return ordinary();
        if(e instanceof MemberReferenceTree t) return ordinary(expr(t.getQualifierExpression()));
        return obj("kind","unsupported","reason","Java expression "+e.getKind());
    }
    static List<Object> body(StatementTree s) {
        if(s==null) return new ArrayList<>();
        if(s instanceof BlockTree b) {
            List<Object> out = new ArrayList<>(); for(var n:b.getStatements()) out.add(stmt(n)); return out;
        }
        return new ArrayList<>(List.of(stmt(s)));
    }
    static Map<String,Object> stmt(StatementTree s) {
        if(s instanceof BlockTree t) return obj("kind","seq","body",body(t));
        if(s instanceof IfTree t) return obj("kind","if","test",expr(t.getCondition()),
                        "then",body(t.getThenStatement()),"else",body(t.getElseStatement()));
        if(s instanceof WhileLoopTree t) return obj("kind","loop","test",expr(t.getCondition()),"body",body(t.getStatement()));
        if(s instanceof DoWhileLoopTree t) return obj("kind","do_loop","test",expr(t.getCondition()),"body",body(t.getStatement()));
        if(s instanceof ForLoopTree t) {
            List<Object> init = new ArrayList<>(), update = new ArrayList<>();
            for(var x:t.getInitializer()) init.add(stmt(x)); for(var x:t.getUpdate()) update.add(stmt(x));
            if(t.getCondition()==null) return obj("kind","unsupported","reason","Java for(;;) requires explicit exit CFG");
            return obj("kind","loop","test",expr(t.getCondition()),"init",init,"update",update,"body",body(t.getStatement()));
        }
        if(s instanceof EnhancedForLoopTree t) return obj("kind","loop","test",ordinary(),"iter",expr(t.getExpression()),"body",body(t.getStatement()));
        if(s instanceof ReturnTree t) return obj("kind","return","expr",expr(t.getExpression()));
        if(s instanceof ThrowTree t) return obj("kind","throw","expr",expr(t.getExpression()));
        if(s instanceof BreakTree t) return obj("kind","break","label",str(t.getLabel()));
        if(s instanceof ContinueTree t) return obj("kind","continue","label",str(t.getLabel()));
        if(s instanceof AssertTree t) return obj("kind","assert","test",expr(t.getCondition()));
        if(s instanceof ExpressionStatementTree t) return obj("kind","basic","expr",expr(t.getExpression()));
        if(s instanceof VariableTree t) return obj("kind","basic","expr",expr(t.getInitializer()));
        if(s instanceof EmptyStatementTree || s instanceof ClassTree) return obj("kind","noop");
        if(s instanceof SynchronizedTree t) return obj("kind","seq","body",List.of(
                            obj("kind","basic","expr",expr(t.getExpression())),stmt(t.getBlock())));
        if(s instanceof SwitchTree t) {
            List<Object> cases = new ArrayList<>();
            for(var c:t.getCases()) {
                List<Object> cs = new ArrayList<>();
                if(c.getStatements()!=null) for(var x:c.getStatements()) cs.add(stmt(x));
                else if(c.getBody() instanceof StatementTree b) cs.add(stmt(b));
                else if(c.getBody() instanceof ExpressionTree e) cs.add(obj("kind","basic","expr",expr(e)));
                // Traditional Java 17 constant-label switches. Pattern switches
                // are rejected rather than silently dropping their guards.
                if(c.getExpressions().isEmpty() && !c.toString().stripLeading().startsWith("default"))
                    return obj("kind","unsupported","reason","Java pattern switch CFG");
                cases.add(obj("labels",c.getExpressions().size(),"default",c.getExpressions().isEmpty(),
                          "body",cs,"fallthrough",c.getCaseKind()==CaseTree.CaseKind.STATEMENT));
            }
            return obj("kind","switch","expr",expr(t.getExpression()),"cases",cases);
        }
        return obj("kind","unsupported","reason","Java statement "+s.getKind());
    }

    static class Unit {
        CompilationUnitTree cu; SourcePositions positions; String path, pkg;
        List<Object> classes=new ArrayList<>(), methods=new ArrayList<>(), warnings=new ArrayList<>();
        Map<String,String> imports=new LinkedHashMap<>(); List<String> wildcards=new ArrayList<>();
        Unit(CompilationUnitTree c, SourcePositions p, String relative) {
            cu=c; positions=p; path=relative; pkg=str(c.getPackageName());
            for(var imp:c.getImports()) {
                String name=imp.getQualifiedIdentifier().toString();
                if(name.endsWith(".*")) wildcards.add(name.substring(0,name.length()-2));
                else imports.put(name.substring(name.lastIndexOf('.')+1),name);
            }
        }
        long start(Tree n) { return positions.getStartPosition(cu,n); }
        long end(Tree n) { return positions.getEndPosition(cu,n); }
        long line(Tree n) { return cu.getLineMap().getLineNumber(Math.max(0,start(n))); }
        void span(Map<String,Object> o, Tree n) {
            o.put("start",start(n)); o.put("end",end(n)); o.put("start_line",line(n));
            o.put("end_line",cu.getLineMap().getLineNumber(Math.max(start(n),end(n)-1)));
        }
        String visibility(ModifiersTree mods, boolean inInterface) {
            Set<Modifier> f=mods.getFlags();
            if(f.contains(Modifier.PUBLIC)) return "public";
            if(f.contains(Modifier.PRIVATE)) return "private";
            if(f.contains(Modifier.PROTECTED)) return "protected";
            return inInterface ? "public":"default";
        }
        void clazz(ClassTree ct, String scope, String parent) {
            if(ct.getSimpleName().toString().isEmpty()) {
                warnings.add("Anonymous class excluded at line "+line(ct)); return;
            }
            String name=ct.getSimpleName().toString(); String qname=scope.isEmpty()?name:scope+"."+name;
            String id="java:"+qname+"@"+path+":"+line(ct);
            boolean inInterface=ct.getKind()==Tree.Kind.INTERFACE || ct.getKind()==Tree.Kind.ANNOTATION_TYPE;
            List<Object> attrs=new ArrayList<>(), mids=new ArrayList<>(), bases=new ArrayList<>(), interfaces=new ArrayList<>();
            if(ct.getExtendsClause()!=null) bases.add(ct.getExtendsClause().toString());
            for(var t:ct.getImplementsClause()) { if(inInterface) bases.add(t.toString()); else interfaces.add(t.toString()); }
            Set<String> fieldNames=new HashSet<>();
            for(var member:ct.getMembers()) if(member instanceof VariableTree v) {
                fieldNames.add(v.getName().toString());
                attrs.add(obj("name",v.getName().toString(),"type",str(v.getType()),
                              "visibility",visibility(v.getModifiers(),inInterface),
                              "static",inInterface || v.getModifiers().getFlags().contains(Modifier.STATIC)));
            }
            Map<String,Object> c=obj("id",id,"qname",qname,"name",name,"path",path,"language","java",
                    "kind",inInterface?"interface":"class","module",pkg,"imports",imports,"wildcard_imports",wildcards,
                    "scope",pkg.isEmpty()?List.of():Arrays.asList(pkg.split("\\.")),"parent_class",parent,
                    "bases",bases,"interfaces",interfaces,"attributes",attrs,"method_ids",mids,
                    "type_refs",new ArrayList<>(),"associations",null,"visibility",visibility(ct.getModifiers(),false));
            span(c,ct); classes.add(c);
            for(var member:ct.getMembers()) {
                if(member instanceof ClassTree nested) clazz(nested,qname,id);
                else if(member instanceof MethodTree m) {
                    String mid=method(m,qname,id,fieldNames,inInterface); mids.add(mid);
                    if(m.getBody()!=null) new TreeScanner<Void,Void>() {
                        @Override public Void visitClass(ClassTree local,Void p) {
                            clazz(local,qname+"."+m.getName()+"@"+line(m),id); return null;
                        }
                    }.scan(m.getBody(),null);
                }
            }
        }
        String method(MethodTree mt,String className,String owner,Set<String> fieldNames,boolean inInterface) {
            String name=mt.getName().toString(); boolean ctor=name.equals("<init>");
            String mid="java:"+className+"."+name+"@"+path+":"+line(mt)+":"+start(mt);
            List<Object> params=new ArrayList<>(); Map<String,String> localTypes=new LinkedHashMap<>();
            Set<String> initial=new HashSet<>();
            for(var p:mt.getParameters()) {
                params.add(obj("name",p.getName().toString(),"type",str(p.getType())));
                initial.add(p.getName().toString()); localTypes.put(p.getName().toString(),str(p.getType()));
            }
            boolean varargs=!mt.getParameters().isEmpty() && mt.getParameters().get(mt.getParameters().size()-1).toString().contains("...");
            Collector collect=new Collector(this,fieldNames,initial,localTypes,className);
            collect.scan(mt.getBody(),null);
            Map<String,Object> m=obj("id",mid,"qname",className+"."+name,"name",name,"owner",owner,
                    "path",path,"language","java","module",pkg,"imports",imports,"wildcard_imports",wildcards,
                    "lexical_parent",null,"visibility",visibility(mt.getModifiers(),inInterface),
                    "static",mt.getModifiers().getFlags().contains(Modifier.STATIC),"constructor",ctor,
                    "receiver_name","this","params",params,"arity_min",varargs ? params.size()-1 : params.size(),"arity_max",varargs ? null : params.size(),
                    "calls",collect.calls,"local_types",localTypes,"field_accesses",collect.accesses,"type_refs",collect.typeRefs,
                    "has_body",mt.getBody()!=null,"abstract",mt.getBody()==null,
                    "ir",body(mt.getBody()),"catch_handlers",collect.catches,"empty_catch_handlers",collect.emptyCatches,
                    "statements",collect.statements,"declarative_statements",collect.declarations,
                    "executable_statements",collect.statements-collect.declarations);
            span(m,mt); methods.add(m); return mid;
        }
    }
    static class Collector extends TreeScanner<Void,Void> {
        Unit u; Set<String> fields; Deque<Set<String>> scopes=new ArrayDeque<>(); String className;
        Map<String,String> localTypes; Set<String> accesses=new TreeSet<>(), typeRefs=new TreeSet<>();
        List<Object> calls=new ArrayList<>(); int catches=0,emptyCatches=0,inHandler=0,statements=0,declarations=0;
        Collector(Unit unit,Set<String> fs,Set<String> initial,Map<String,String> types,String cls) {
            u=unit;fields=fs;scopes.push(new HashSet<>(initial));localTypes=types;className=cls;
        }
        boolean local(String name) { for(var s:scopes) if(s.contains(name)) return true; return false; }
        @Override public Void scan(Tree tree,Void p) {
            if(tree instanceof StatementTree && !(tree instanceof BlockTree)) {
                statements++; if(tree instanceof VariableTree || tree instanceof ClassTree) declarations++;
            }
            return super.scan(tree,p);
        }
        @Override public Void visitClass(ClassTree t,Void p) { return null; }
        @Override public Void visitLambdaExpression(LambdaExpressionTree t,Void p) { u.warnings.add("Lambda body excluded from named-callable metrics at line "+u.line(t)); return null; }
        @Override public Void visitBlock(BlockTree t,Void p) {
            scopes.push(new HashSet<>()); super.visitBlock(t,p); scopes.pop(); return null;
        }
        @Override public Void visitForLoop(ForLoopTree t,Void p) {
            scopes.push(new HashSet<>());super.visitForLoop(t,p);scopes.pop();return null;
        }
        @Override public Void visitEnhancedForLoop(EnhancedForLoopTree t,Void p) {
            scopes.push(new HashSet<>());super.visitEnhancedForLoop(t,p);scopes.pop();return null;
        }
        @Override public Void visitVariable(VariableTree t,Void p) {
            scan(t.getInitializer(),p); scopes.peek().add(t.getName().toString());
            String type=str(t.getType());
            if(type.equals("var") && t.getInitializer() instanceof NewClassTree nc) type=nc.getIdentifier().toString();
            String name=t.getName().toString();
            if(localTypes.containsKey(name) && !localTypes.get(name).equals(type)) localTypes.put(name, "<ambiguous-local-type>");
            else localTypes.put(name,type);
            typeRefs.add(type);return null;
        }
        @Override public Void visitIdentifier(IdentifierTree t,Void p) {
            String name=t.getName().toString(); if(fields.contains(name) && !local(name)) accesses.add(name); return null;
        }
        @Override public Void visitMemberSelect(MemberSelectTree t,Void p) {
            String recv=t.getExpression().toString(), name=t.getIdentifier().toString();
            if((recv.equals("this") || recv.equals(className) || recv.equals(className.substring(className.lastIndexOf('.')+1))) && fields.contains(name)) accesses.add(name);
            scan(t.getExpression(),p); return null;
        }
        @Override public Void visitMethodInvocation(MethodInvocationTree t,Void p) {
            ExpressionTree selected=t.getMethodSelect();String name,recv;
            if(selected instanceof MemberSelectTree ms) { name=ms.getIdentifier().toString(); recv=ms.getExpression().toString();scan(ms.getExpression(),p); }
            else { name=selected.toString();recv=""; }
            calls.add(obj("name",name,"receiver",recv,"arity",t.getArguments().size(),"line",u.line(t),"in_handler",inHandler>0,"kind","call"));
            for(var a:t.getArguments()) scan(a,p);return null;
        }
        @Override public Void visitNewClass(NewClassTree t,Void p) {
            String type=t.getIdentifier().toString();typeRefs.add(type);
            calls.add(obj("name","<init>","receiver",type,"arity",t.getArguments().size(),"line",u.line(t),"in_handler",inHandler>0,"kind","constructor"));
            scan(t.getEnclosingExpression(),p);for(var a:t.getArguments())scan(a,p);return null;
        }
        @Override public Void visitTypeCast(TypeCastTree t,Void p) { typeRefs.add(t.getType().toString());scan(t.getExpression(),p);return null; }
        @Override public Void visitInstanceOf(InstanceOfTree t,Void p) { if(t.getType()!=null)typeRefs.add(t.getType().toString());scan(t.getExpression(),p);return null; }
        @Override public Void visitCatch(CatchTree t,Void p) {
            catches++; if(t.getBlock().getStatements().stream().allMatch(x->x instanceof EmptyStatementTree))emptyCatches++;
            scopes.push(new HashSet<>(Set.of(t.getParameter().getName().toString())));inHandler++;
            scan(t.getBlock(),p);inHandler--;scopes.pop();return null;
        }
    }
    public static void main(String[] args) throws Exception {
        if(args.length!=1) throw new IllegalArgumentException("Expected manifest path");
        JavaCompiler compiler=ToolProvider.getSystemJavaCompiler();
        if(compiler==null) throw new IllegalStateException("A JDK, not only a JRE, is required");
        Map<String,String> relative=new HashMap<>();List<File> files=new ArrayList<>();
        for(String line:Files.readAllLines(Path.of(args[0]),StandardCharsets.UTF_8)) {
            String[] p=line.split("\t",-1);
            String rel=new String(Base64.getDecoder().decode(p[0]),StandardCharsets.UTF_8);
            String abs=new String(Base64.getDecoder().decode(p[1]),StandardCharsets.UTF_8);
            File f=new File(abs);files.add(f);relative.put(f.toPath().toAbsolutePath().normalize().toString(),rel);
        }
        DiagnosticCollector<JavaFileObject> diagnostics=new DiagnosticCollector<>();
        try(StandardJavaFileManager fm=compiler.getStandardFileManager(diagnostics,Locale.ROOT,StandardCharsets.UTF_8)) {
            JavacTask task=(JavacTask)compiler.getTask(null,fm,diagnostics,List.of("-proc:none","-encoding","UTF-8"),null,fm.getJavaFileObjectsFromFiles(files));
            List<CompilationUnitTree> units=new ArrayList<>(); for(var cu:task.parse())units.add(cu);
            SourcePositions positions=Trees.instance(task).getSourcePositions();
            for(var cu:units) {
                String uri=Path.of(cu.getSourceFile().toUri()).toAbsolutePath().normalize().toString();
                String rel=relative.getOrDefault(uri,cu.getSourceFile().getName());
                Unit u=new Unit(cu,positions,rel);
                List<Object> errors=new ArrayList<>();
                for(var d:diagnostics.getDiagnostics()) if(d.getKind()==Diagnostic.Kind.ERROR && d.getSource()!=null && d.getSource().toUri().equals(cu.getSourceFile().toUri()))
                    errors.add(obj("line",d.getLineNumber(),"message",d.getMessage(Locale.ROOT)));
                if(errors.isEmpty()) for(var decl:cu.getTypeDecls()) if(decl instanceof ClassTree ct)u.clazz(ct,u.pkg,null);
                // Count once over the complete compilation-unit syntax tree.
                // Blocks and formal/catch/lambda parameters are not statements;
                // class, method and variable declarations are declaration nodes.
                final int[] counts={0,0};
                new TreeScanner<Void,Void>() {
                    Set<Tree> parameters=Collections.newSetFromMap(new IdentityHashMap<Tree,Boolean>());
                    @Override public Void scan(Tree t,Void ignored) {
                        if(t==null) return null;
                        if(t instanceof MethodTree m) { parameters.addAll(m.getParameters()); counts[0]++; counts[1]++; }
                        if(t instanceof CatchTree c) parameters.add(c.getParameter());
                        if(t instanceof LambdaExpressionTree l) parameters.addAll(l.getParameters());
                        if(t instanceof StatementTree && !(t instanceof BlockTree) && !parameters.contains(t)) {
                            counts[0]++; if(t instanceof VariableTree || t instanceof ClassTree) counts[1]++;
                        }
                        return super.scan(t,ignored);
                    }
                }.scan(cu,null);
                int stmts=counts[0],decls=counts[1];
                System.out.println(json(obj("path",rel,"language","java","module",u.pkg,"classes",u.classes,"methods",u.methods,
                    "warnings",u.warnings,"parse_ok",errors.isEmpty(),"errors",errors,
                    "metrics",obj("statements",stmts,"declarative_statements",decls,"executable_statements",stmts-decls))));
            }
        }
    }
}
