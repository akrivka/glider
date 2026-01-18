# Architectural overview/plan for glider.

There will be two main first-party components:
* glider-operator - written in Python, it will contain both the API and the workers
* glider-web - written in TypeScript and SvelteKit

Additionally, we'll use two other important technologies:
* SurrealDB - everything database
* Temporal - durable execution and scheduling

The deployment will be split into 4 containers:
* API + frontend - built from the glider-operator image with `glider/entrypoint_api.py`
* workers - also built from the glider-operator image with `glider/entrypoint_worker.py`
* Temporal
* SurrealDB

Additionaly, let's also deploy Temporal UI and SurrealDB UI (if there is one).


## Tasks

1. [ ] Create the basic @docker-compose.yaml with all the containers, @glider-operator/Dockerfile, and fill-out @glider-operator/glider/entrypoint_worker.py with a basic Temporal worker. Connect the dots by adding a sample workflow in @glider-operator/glider/workflows and one API endpoint that runs it and one that recovers the status in @glider-operator/glider/api. Add a page on the frontend with a button to call that endpoint and poll the status.
2. [ ] TBD