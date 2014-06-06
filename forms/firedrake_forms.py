from forms import Forms
from firedrake import *
from pyop2.ir.ast_plan import V_OP_UAJ
from pyop2.profiling import get_timers

parameters["assembly_cache"]["enabled"] = False
parameters["coffee"]["licm"] = True
parameters["coffee"]["ap"] = True
parameters["coffee"]["vect"] = (V_OP_UAJ, 1)


def mass(p, q, dim, mesh):
    V = FunctionSpace(mesh, 'CG', p)
    Q = FunctionSpace(mesh, 'CG', q)
    u = TrialFunction(V)
    v = TestFunction(V)
    it = dot(v, u)
    f = [Function(Q).assign(1.0) for _ in range(3)]
    return it, f, lambda x: x


def elasticity(p, q, dim, mesh):
    V = VectorFunctionSpace(mesh, 'CG', p)
    Q = FunctionSpace(mesh, 'CG', q)
    u = TrialFunction(V)
    v = TestFunction(V)
    eps = lambda v: grad(v) + transpose(grad(v))
    it = 0.25*inner(eps(v), eps(u))
    f = [Function(Q).assign(1.0) for _ in range(3)]
    return it, f, lambda x: x


def poisson(p, q, dim, mesh):
    V = VectorFunctionSpace(mesh, 'CG', p)
    Q = VectorFunctionSpace(mesh, 'CG', q)
    u = TrialFunction(V)
    v = TestFunction(V)
    it = inner(grad(v), grad(u))
    f = [Function(Q).assign(1.0) for _ in range(3)]
    return it, f, div


def mixed_poisson(p, q, dim, mesh):
    BDM = FunctionSpace(mesh, "BDM", p)
    DG = FunctionSpace(mesh, "DG", p - 1)
    Q = FunctionSpace(mesh, 'CG', q)
    W = BDM * DG
    sigma, u = TrialFunctions(W)
    tau, v = TestFunctions(W)
    it = dot(sigma, tau) + div(tau)*u + div(sigma)*v
    f = [Function(Q).assign(1.0) for _ in range(3)]
    return it, f, lambda x: x


class FiredrakeForms(Forms):
    series = {'np': op2.MPI.comm.size, 'variant': 'Firedrake'}

    def forms(self, p=1, q=1, dim=3, form='mass'):
        if dim == 2:
            mesh = UnitSquareMesh(31, 31)
            normalize = 1.0
        if dim == 3:
            size = int(18.0 / (p+q))
            normalize = 1000.0 / (size+1)**3
            mesh = UnitCubeMesh(size, size, size)
        it, f, m = eval(form)(p, q, dim, mesh)
        A = assemble(it*dx)

        for nf in range(4):
            with self.timed_region('nf %d' % nf, normalize):
                assemble(reduce(inner, map(m, f[:nf]) + [it])*dx, tensor=A)
                A.M
        for task, timer in get_timers(reset=True).items():
            self.register_timing(task, timer.total)

if __name__ == '__main__':
    op2.init(log_level='WARNING')
    from ffc.log import set_level
    set_level('ERROR')

    FiredrakeForms().main()
