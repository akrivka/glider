# Google Calendar and Spotify integration

We will add two scheduled Temporal workflows that will pull data from Google Calendar and Spotify respectively, and store them in SurrealDB. Then, we'll add a simple UI to visualize them.

## Phase 1 - Google Calendar

Step 1: We will have to figure out how to authenticate with my personal Google account. Reminder that this is a personal app that will be deployed on my personal server. So storing credentials locally is permissible. The token might need to be refreshed after some time. Come up with a basic representation of events in SurrealDB, feel free to use unstructured data / schemaless for now. Create a Temporal workflow with a schedule to poll Google Calendar (I don't assume it'd be good to set up some kind of webhooks) every now and then (30 minutes?) and store data in SurrealDB.

Step 2: Make a simple Calendar UI to visualize the data in a separate page of the frontend. Start with a weekly view similar to the Google Calendar weekly view, but with not interactivity features other then arrows left and right to go backward and forward in time. 

## Phase 2 - Spotify

Step 1: For Spotify, we want to watch/observe what I'm listening to in ~real time. Polling the Spotify player state seems easiest - it's okay if there's some delay/potentially missed songs (I mostly care about songs I've actually listened to, not skipped through), in other words, feel free to add some reasonable debounce, if that makes sense. Otherwise same deal: figure out how to authenticate with Spotify, come up with a representation of "listened to X at time T" in the DB, and (probably) wrap this into a Temporal workflow.

Step 2: Make a simple daily view that combines the Google Calendar and Spotify integration. For simplicity, show only one day (in a similar vertical fashion like the weekly calendar view) with the calendar events as the main boxes and the Spotify listening to the side. Merge the Spotify blocks into listening segments, with the possibility to hover over them to get more info about what was listened to. Cut corners / make it simpler if necessary.