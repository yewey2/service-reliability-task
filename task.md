**Service Reliability Take-Home – ATS Take-Home Assignment**

**Overview:**
Your team operates multiple internal web services that power government applications. Some are legacy systems, others are new, deployed across different environments (ECS, EC2, or even manually). After deployments, there’s often no clear, consistent way to tell if a service is running properly, returning the expected version, or showing degraded performance.

**Objective:**
Design and implement a lightweight Service Reliability solution that periodically checks multiple service endpoints, detects availability or version issues, and displays the latest health information in a simple, clear way.

**Core Requirements:**
1. Accept a list or configuration file of services (name, URL, expected version).
2. Periodically ping each service and record its status, latency, and version (if available).
3. Store results persistently (SQLite, JSON file, or database).
4. Expose results through a minimal API or dashboard.
5. Provide a Dockerfile (and optionally docker-compose.yml) to run the app easily.

**Stretch Goals (Optional):**
- Detect version drift (deployed version differs from expected).
- Group services by environment (staging, production).
- Add simple alerting (console, webhook, or email on repeated failures).
- Add an AI-generated summary of recent incidents.
- Write a short (≤300 words) infrastructure note explaining how you’d deploy and monitor this in production.

**Deliverables:**
- Source code in a repository (GitHub or zip).
- README.md with:
  - Quickstart instructions.
  - Design overview and trade-offs.
  - Infrastructure/deployment notes.
  - Optional screenshots or demo GIF.

**Evaluation Focus:**
- **Problem Solving** – clarity of approach and simplification.
- **Code Structure** – organization, maintainability, and readability.
- **Full-Stack Capability** – functioning API/UI, persistence, Dockerisation.
- **Operational Thinking** – observability, deployment awareness, fault handling.
- **Communication** – clear README and rationale.

**Guidance:**
This assignment is intentionally open-ended. Focus on delivering a working, well-thought-out solution within a reasonable effort (typically one evening). Junior engineers may prioritize the core functionality, while more experienced engineers can demonstrate additional depth — such as alerting, version tracking, or deployment design. The goal is to see how you reason about trade-offs, structure your work, and ensure reliability end-to-end.

**Time Expectation:**
This assignment is intentionally scoped to be achievable in under 5 hours of focused work. We’re not assessing how much you can build, but how well you simplify, reason, and deliver within realistic constraints. Please plan your effort accordingly — a smaller, thoughtful solution is preferred over an overbuilt one.

**AI Usage (Encouraged):**
You are encouraged to use AI tools (such as ChatGPT, GitHub Copilot, Claude, or others) to assist in solving this assignment — just as you might in real work. Please document briefly in your README how and where AI helped you. For example:
- Generating code snippets or boilerplate.
- Debugging errors or refactoring.
- Brainstorming architecture, naming, or documentation.

The goal is to assess your ability to use AI effectively and responsibly, not to avoid it.