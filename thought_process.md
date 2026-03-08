# Thought process and notes (done by human)

# Start: 2.08pm

## Requirements portion
"Accept a list or configuration file of services (name, URL, expected version)."

- Likely will need to accept different errors as well, e.g. 403 unauthorized, 500 internal server error, etc. 
- Ensure that there are other parameters that we can include
  - HOWEVER, make sure that these are not maliciously injected...
  
"Periodically ping each service and record its status, latency, and version (if available)."

- Can host on something like FastAPI, job + alert?
- Alerts should be able to trigger other pipeline flows / inform users of failures.

"Store results persistently (SQLite, JSON file, or database)."

- Weighing pros and cons
  - SQLite / JSON file: lightweight, can deploy directly.
    - But maintaining it may be concern. Especially JSON file / SQLite, may bloat the entire repository
  - Database: likely a better alternative
    - To consider - SQL or NoSQL? 
      -  NoSQL can likely scale better if there are other variables required, e.g. more than version history
      -  But IF only a few columns required, then SQL is ok. Use SQLite.
    - Downside: Likely will have associated costs once project becomes bigger...
      - Meaning we likely need to purge on a periodic basis to maintain size...
- Purge constraints: 
  - depends on how much data we are expecting. 
  - Likely can leave it to every year

"Expose results through a minimal API or dashboard."

- minimal API preferred.
- Dashboard can be created using simple frontend framework, hosted to call the same FastAPI backend
- Or built directly in the same backend that serves a simple HTML page
  - Pros: easier to manage since only 1 repo
  - Cons: harder to scale separately. may get messy in the future especially if multiple developers are working on frontend / backend separately
  - Decide to do up dashboard in same environment for easier management and submission. In the future, if we want to scale up, likely require a separate service for ease of maintenance.

"Provide a Dockerfile (and optionally docker-compose.yml) to run the app easily."

- Simple Dockerfile will do, just copy and run
- REMEMBER: to actually test using Docker and make sure no errors / bugs

"Detect version drift (deployed version differs from expected)"

- make sure to track whether bugs are due to versioning issues. 
- simplest method: include the version number in the health check to see if it is the ***right version!!***

"Group services by environment (staging, production)"

- can serve different endpoints for different environments. 
  - pros: separate traffic means ease of management
  - cons: increased costs for multiple hosts

"Add simple alerting (console, webhook, or email on repeated failures)."

- good to add alerts - especially for devs. If service is down, will let developers know
- HOWEVER: security is a concern, ensure that webhook need to have adequate security. 
- If personal project: can use simple bot solutions e.g. Telegram bot. 
- If for corporate: better to use email with email groupings. Can explore: Slack / Teams bot integration to alert developers


"Add an AI-generated summary of recent incidents."

- AI generated summary improves readability of incidents, no need to enter into dashboard and manually check. 
- Better if AI can be a chatbot to pull data
- Concerns: AI hosting, AI token costs, security risks (if using public AI providers e.g. Gemini / OpenAI) 
- Plan: work on this once dashboard is up. Since bot will be able to pull data, can use a simple retrieval augmented geneartion system, with the incident tags or error timings as filters. 


# Other concerns

- How often to do polling for health checks? 
  - Likely depending on service... Non-essential e.g. pipeline runs can do once daily. But live services likely require frequent (e.g. 60 seconds?)

- Degraded performance mentioned in overview
  - Means the service is still up, but has issues (e.g. lagging). To include a check for total time taken for each service to respond, and raise alert / warning if it takes too long? (e.g. >1 second for health check?)

- For list of endpoints, how to store?
  - Can create a JSON or YAML locally, then for different versions, we can version control using git. 
  - As opposed to database...? may be overkill to keep polling same database multiple times
- Also for endpoints, need to take note of the following
  - Health endpoint? ("/health", "health-check" etc, depending on who created the endpoint... likely hard to standardize since the endpoints are created by developers from other units / groups)
  - Version control available? and their respective data (is it in a JSON with {"version": "1.x.x"}? or returning plaintext...? also depends on who created the endpoint)
  - status code. is 2XX good enough? to include this in the endpoint JSON as well!

# Compiled ~2.30pm (30 minute to look at task + write down thoughts)