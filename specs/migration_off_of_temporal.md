I'm considering migrating this project away from using Temporal, to using a simple single-threaded asyncio loop with basic scheduling. 

I initially chose to use Temporal, because I was familiar with it, since we use it at work. But since this is only a personal app, meant to be used by exactly one person, the workloads here are probably very small compared to the scale Temporal is usually used at.

You can see in the current architecture that there is always exactly one worker polling the Temporal queue `glider-tasks`. So there's not much orchestration/coordination going on, mainly just the durability.

But durability is also not really a big concern for me here, since all of my workloads are basically about syncing external data into the glider SurrealDB, for rednering and processing on the web frontend (and potentially other applications later).

This project also used to have an API entrypoint, but I think those endpoints will mostly be only reading the DB or doing operations that can be done within the handler.

I think the project would potentially simplify a lot if I got rid of Temporal, especiall the Nix module and deployment (it has been giving me a lot of headache).

The alternative architecture I'm thinking off is that the sync schedules are specified in a config.toml file, and there's an entrypoint something like `run_worker.py` which uses asyncio to call each of the sync functions at the specified schedule. If the worker is restarted, it simply restarts the schedules by running each sync and then awaiting. Each sync function is also runnable individually from its main file for easy development and debugging (this has also been a painpoint previously). The details of the asyncio plumbing need to be figured out, I'm open to using some small library.

====

Take time to understand the project and evaluate the proposal above: get rid of Temporal, use simple asyncio loop.
