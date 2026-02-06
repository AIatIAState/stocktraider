# ai-stock-trading
COMS 599 Creative Component

View our latest progress! (Yay CICD)

Deployed app URL: `http://coms-4020-002.class.las.iastate.edu:8080`
Health endpoint: `http://coms-4020-002.class.las.iastate.edu:8080/api/health`
Readiness endpoint (checks DB): `http://coms-4020-002.class.las.iastate.edu:8080/api/ready`

What: Although LLMs have many applications, using them for stock and crypto trading often relies on paid subscription platforms built on closed-source models (e.g., https://quant.drnamlabs.com/). In this work, we aim to evaluate and improve open-source LLMs for trading-related tasks. Our project has two phases: (1) building a historical trading dataset, and (2) integrating LLM techniques—such as fine-tuning and preference optimization—into a platform that can automatically suggest trading actions and summarize current market conditions.

Users: small businesses, students.

Features: - View market condition.
- Seeing status or each ticket.
- Perform virtual trade (note, the application of this work is for simulating the market. No actual funding investment is performed in the application).
- Showing percentage of winning trade.

UseCases: A person who do trading for stock/ crypto
A student who wants to learn more about stocking and finance.

Example: John wants to do trading but he didn't know about what types of stock he can make profit from investment.


# Installation

To install the necessary dependencies for the ai-stock-trading project, please follow these steps:

1. Clone the repository to your local machine:

   ```bash
   git clone https://github.com/MasonInman29/ai-stock-trading.git
    cd ai-stock-trading
    ```

2. Start your Docker daemon if it's not already running.

    Linux:
    ```bash
    sudo systemctl start docker 
    ```
    Windows/Mac: 
    ```bash
    docker desktop start
   ```
3. Start the docker containers:

   ```bash
   docker compose up --build
   ```
   
4. Access the application:

    Open your web browser and navigate to `http://localhost:8080` to access the ai-stock-trading application.

    The backend API is served from the same origin under `http://localhost:8080/api/*`


# CI/CD

We have setup CI/CD pipelines that proxy through port 8080 to align with university server firewall restrictions.

## Serving everything through 8080

- Port: `8080` only
- `web` container: Nginx serves the built Vite app and proxies `/api/*` to the backend
- `fastapi` container: API listens on `5000` internally (on the server side). This means the browser calls `http://<host>:8080/api/...` and never needs direct access to `:5000`.

## CI pipeline (build test)

In `.gitlab-ci.yml`, the `build_images` job runs on:

- Merge Request pipelines
- `main` branch pipelines

It performs a basic build check by running `docker compose build`.

## CD pipeline (deploy)

In `.gitlab-ci.yml`, `deploy_production`:

- Runs only on `main`
- Uses the GitLab runner tagged `deployment`
- Deploys with `docker compose up -d --build`
- Performs a smoke check by requesting `http://web:8080/api/ready` from inside the Docker network

If successful, it is deployed:
Deployed app URL: `http://coms-4020-002.class.las.iastate.edu:8080`
Health endpoint: `http://coms-4020-002.class.las.iastate.edu:8080/api/health`
Readiness endpoint (checks DB): `http://coms-4020-002.class.las.iastate.edu:8080/api/ready`

