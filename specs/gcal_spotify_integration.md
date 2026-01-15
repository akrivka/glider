# Google Calendar and Spotify integration

We will add two scheduled Temporal workflows that will pull data from Google Calendar and Spotify respectively, and store them in SurrealDB. Then, we'll add a simple UI to visualize them.

## Phase 1

In Phase 1, we'll focus only on the Google Calendar integration. 

Step 1: We will have to figure out how to authenticate with my personal Google account. Reminder that this is a personal app that will be deployed on my personal server. So storing credentials locally is permissible. The token might need to be refreshed after some time. Come up with a basic representation of events in SurrealDB, feel free to use unstructured data / schemaless for now. Create a Temporal workflow with a schedule to poll Google Calendar (I don't assume it'd be good to set up some kind of webhooks) every now and then (30 minutes?) and store data in SurrealDB.

Step 2: Make a simple Calendar UI to visualize the data in a separate page of the frontend. Start with a weekly view similar to the Google Calendar weekly view, but with not interactivity features other then arrows left and right to go backward and forward in time. You'll probably have to add API endpoints for this. 

## Phase 2

TBD (Spotify integration)