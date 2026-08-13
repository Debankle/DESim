# DESim
 
A cloud-hosted differential equation simulator. Configure parameters for a 2D heat equation, 2D wave equation, or diffusion-advection equation, submit a job, and download the result as an HDF5 file once it's done. Public simulations can be browsed and filtered by other users.
 
## How it works
 
Requests come in through a Next.js frontend and a NestJS API, get queued via SQS, and picked up by a simulation worker running the numerical solver. Finished jobs are stored in S3, with metadata tracked in Postgres. Everything runs as containerised microservices on ECS Fargate, split so the simulation workers scale independently based on queue backlog rather than CPU load — a handful of heavy jobs shouldn't trigger the same scaling logic as a burst of UI traffic.
 
## Numerical solver
 
The core solver is a θ-method time integrator. For implicit steps, the resulting nonlinear system is solved with a Jacobian-Free Newton-Krylov method — Jacobian-vector products are approximated via finite differences rather than ever forming the Jacobian explicitly, then solved with GMRES. Optional backtracking line search included.
 
## Stack
 
Python (solver, API), Next.js, NestJS, PostgreSQL, AWS (ECS, SQS, S3, Cognito, CloudFront), AWS CDK
 
## Note
 
Infrastructure/deployment configuration has been left out of this repo, since it references account-specific resources — this is the application code only.

