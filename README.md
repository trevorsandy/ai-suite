# AI-Suite

**AI-Suite** extends [n8n-io](https://github.com/n8n-io) [Self-hosted
AI Starter Kit](https://github.com/n8n-io/self-hosted-ai-starter-kit)
intended to be an **end-to-end path from zero to working AI workflows** for
developers and those who want to enabe a local, private AI solution.

It provides an open, curated, pre-configured docker compose template that
bootstraps a fully featured Local AI and Low Code development environment on a
self-hosted n8n platform, enabling users to focus on building AI workflows.

![n8n.io - n8n](https://raw.githubusercontent.com/trevorsandy/ai-suite/main/assets/n8n-demo.gif)

Curated by <https://github.com/trevorsandy>.

## What’s included

✅ [**Self-hosted n8n**](https://n8n.io/) - Low-code platform with over 400
integrations and advanced AI components

✅ [**Open WebUI**](https://openwebui.com/) - ChatGPT-like interface to
privately interact with your local models and N8N agents

✅ [**Ollama**](https://ollama.com/) - Cross-platform LLM platform to install
and run the latest local LLMs

✅ [**Supabase**](https://supabase.com/) - Open source database as a service,
most widely used database for AI agents

✅ [**Flowise**](https://flowiseai.com/) - No/low code AI agent builder that
pairs very well with n8n

✅ [**Qdrant**](https://qdrant.tech/) - Open source, high performance vector
store with an comprehensive API.

✅ [**PostgreSQL**](https://www.postgresql.org/) -  Workhorse of the Data
Engineering world, backend for Langfuse.

✅ [**Neo4j**](https://neo4j.com/) - Knowledge graph engine that powers tools
like GraphRAG, LightRAG, and Graphiti.

✅ [**SearXNG**](https://searxng.org/) - Open source internet metasearch engine
, aggregates results from up to 229 search services.

✅ [**Langfuse**](https://langfuse.com/) - Open source LLM engineering platform
for agent observability

✅ [**Caddy**](https://caddyserver.com/) - Managed HTTPS/TLS for custom domains.

## Prerequisites

Before you begin, make sure you have the following software installed:

- [Python](https://www.python.org/downloads/) - Required to run the setup script
- [Git/GitHub Desktop](https://desktop.github.com/) - For easy repository management.
- [Docker/Docker Desktop](https://www.docker.com/products/docker-desktop/) -
Required to setup and run all ai-suite services.

   <details>
   <summary>Docker Compose commands</summary>

   If you are using a machine without the `docker compose` command available by
   default, run these commands to install Docker compose:

   ```bash
   DOCKER_COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/
   releases/latest | grep 'tag_name' | cut -d\\" -f4)
   sudo curl -L "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-linux-x86_64" -o /usr/local/bin docker-compose
   sudo chmod +x /usr/local/bin/docker-compose
   sudo mkdir -p /usr/local/lib/docker/cli-plugins
   sudo ln -s /usr/local/bin/docker-compose /usr/local/lib/docker/cli-plugins/docker-compose
   ```

   </details>

## Installation

1. Clone the repository and navigate to the project directory:

   ```bash
   git clone https://github.com/trevorsandy/ai-suite.git
   cd ai-suite
   ```

2. Make a copy of `.env.example` renamed to `.env` in the project directory.

   ```bash
   cp .env.example .env # update secrets and passwords inside
   ```

3. Set the following required environment variables:

   <details>
   <summary>Credential environment variables</summary>

   ```bash
   ############
   # Generating Credentials
   # OpenSSL: Available by default on Linux/Mac via command `openssl rand -hex 32`
   #   For Windows, use 'WSL2', 'Git Bash' terminal installed with git or from cmd
   #   run the command: python -c "import secrets; print(secrets.token_hex(32))"
   # 
   # Password: Use Python command to generate 16-character strong password:
   #   python3 -c "import secrets;import string; alphabet = string.ascii_letters + string.   digits;\
   #               password = ''.join(secrets.choice(alphabet) for i in range(16));\
   #               print(password)"
   ############

   ############
   # Supabase
   ############
   JWT_SECRET=
   ANON_KEY=
   SERVICE_ROLE_KEY=
   DASHBOARD_USERNAME=
   DASHBOARD_PASSWORD=
   POOLER_TENANT_ID=

   ############
   # Postgres
   ############
   ...
   POSTGRES_PASSWORD=your-super-secret-postgres-password # use Password

   ############
   # Flowise
   ############
   FLOWISE_USERNAME=ai_suite_user
   FLOWISE_PASSWORD=your-super-secret-postgres-password # use Password

   ############
   # n8n 
   ############
   FLOWISE_USERNAME=ai_suite_user
   FLOWISE_PASSWORD=your-super-secret-postgres-password # use Password

   N8N_ENCRYPTION_KEY=super-secret-key             # use OpenSSL
   N8N_USER_MANAGEMENT_JWT_SECRET=even-more-secret # use OpenSSL
   ```

   </details>

> [!IMPORTANT]
> Make sure to generate secure random values for all secrets. Never use the
> example values in production.

---

The installation command accepts an optional `--profile` argument to specify
which GPU configuration to use.

**AI-Suite** includes a `start_services.py` script that handles the setup of
Supabase and starting both Supabase and AI services.

Before running `start_services.py`, setup the Supabase environment variables
using their [self-hosting guide](https://supabase.com/docs/guides/self-hosting/docker#securing-your-services).

### For Nvidia GPU users

```bash
python start_services.py --profile gpu-nvidia
```

> [!NOTE]
> If you have not used your Nvidia GPU with Docker before, please follow the
> [Ollama Docker instructions](https://github.com/ollama/ollama/blob/main/docs/docker.md).

### For AMD GPU users on Linux

```bash
python start_services.py --profile gpu-amd
```

### For Mac / Apple Silicon or running OLLAMA in the Host

If you're using a Mac with an M1 or newer processor, you can't expose your GPU
to the Docker instance, unfortunately. There are two options in this case:

1. Run ai-suite fully on CPU:

   ```bash
   python start_services.py --profile cpu
   ```

2. Run Ollama on your Host for faster inference, and connect to that from the
   n8n instance:

   ```bash
   python start_services.py --profile none
   ```

   If you want to run Ollama on your Mac, check the [Ollama homepage](https://ollama.com/)
   for installation instructions.

#### For users running OLLAMA in the Host

If you're running OLLAMA in your Docker Host (not in Docker), modify the
OLLAMA_HOST environment variable in the n8n service configuration and update the
x-n8n section in your Docker Compose file as follows:

```yaml
x-n8n: &service-n8n
  # ... other configurations ...
  environment:
    # ... other environment variables ...
    - OLLAMA_HOST=host.docker.internal:11434
```

Additionally, after you see "Editor is now accessible via: <http://localhost:5678/>":

1. Head to <http://localhost:5678/home/credentials>
2. Click on "Local Ollama service"
3. Change the base URL to "`http://host.docker.internal:11434/`"

### For everyone else

```bash
python start_services.py --profile cpu
```

### The environment argument

The `start_services.py` script supports a **private** (default) and **public**
environment argument:

- **private:** you are deploying the stack in a safe environment, all AI-Suite
ports are accessible
- **public:** the stack is deployed in a public environment, all AI-Suite ports
except _80_ and _443_ are closed

The AI-Suite stack is initialized with...

```bash
python start_services.py --profile gpu-nvidia --environment private
```

which is equal to being initialized with:

```bash
python start_services.py --profile gpu-nvidia
```

## Deploying to the Cloud

### Prerequisites for the below steps

- Linux machine (preferably Unbuntu) with Nano, Git, and Docker installed

### Extra steps

Before running the above commands to pull the repo and install everything:

> [!WARNING]
> ufw does not shield ports published by docker, because the iptables rules
> configured by Docker are analyzed before those configured by ufw. There is a
> solution to change this behavior, but that is out of scope for this project.
> Just make sure that all traffic runs through the Caddy service via port _443_.
> Port _80_ should only be used to redirect to port _443_.

1. Run the commands as root to open up the necessary ports:

    ```bash
    ufw enable
    ufw allow 80 && ufw allow 443
    ufw reload
    ```

2. Run the `start_services.py` script with the environment argument **public**
   to indicate you are going to run the package in a public environment. The
   script will make sure that all ports, except for _80_ and _443_, are closed
   down, e.g.

   ```bash
   python3 start_services.py --profile gpu-nvidia --environment public
   ```

3. Set up A records for your DNS provider to point your subdomains you'll set
   up in the .env file for Caddy to the IP address of your cloud instance.

   For example, A record to point n8n to [cloud instance IP] for n8n.yourdomain.com

> [!NOTE]
> If you are using a cloud machine without the "docker compose" command
> available by default such as a Ubuntu GPU instance on DigitalOcean, run these
> commands before running start_services.py:

<details>
<summary>Docker Compose setup commands</summary>
  
```bash
DOCKER_COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep 'tag_name' | cut -d\\" -f4)
sudo curl -L "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-linux-x86_64" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
sudo mkdir -p /usr/local/lib/docker/cli-plugins
sudo ln -s /usr/local/bin/docker-compose /usr/local/lib/docker/cli-plugins/docker-compose
```

</details>

## ⚡️ Quick start and usage

The main component of the self-hosted AI-Suite is a docker compose file
pre-configured with network and disk so there isn’t much else you need to
install. After completing the installation steps above, follow the steps below
to get started.  

Use the settings specified below to upate Credentials.

- Local Ollama service: base URL <http://ollama:11434/> (n8n config), <http://localhost:11434/>
(browser)

- Local QdrantApi database: base URL <http://qdrant:6333/> (n8n config), <http://localhost:6333/>
(browser)

- Google Drive: Follow [this guide from n8n](https://docs.n8n.io/integrations/builtin/credentials/google/).

- Postgres account (through Supabase): use _db_, _username_, and _password_ from
  .env.

> [!IMPORTANT]
> Host is 'db' since that is the name of the service running Supabase.  
<!-- -->
> [!NOTE]
> If you are running OLLAMA on your Host, for the credential _Local Ollama
> service_, set the base URL to <http://host.docker.internal:11434/> and set
> _Local QdrantApi database_ to <http://host.docker.internal:6333/>.
>
> Don't use _localhost_ for the redirect URI, instead, use another domain.
> It will still work!
> Alternatively, you can set up [local file triggers](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.localfiletrigger/).

1. Open <http://localhost:5678/> in your browser to set up n8n. You’ll only
   have to do this once. You are NOT creating an account with n8n in the setup here,
   it is only a local account for your instance!

2. Open the [Demo workflow](http://localhost:5678/workflow/srOnR8PAY3u4RSwb) and
   set the base URL for _Local Ollama service_.

3. Select **Test workflow** to confirm the workflow is properly configured.

4. If this is the first time you’re running the workflow, you may need to wait
   until Ollama finishes downloading the specified model. You can inspect the
   docker console logs to check on the progress.

5. Toggle the _Demo workflow_ as active and treat the _RAG AI Agent_ workflows.

   <details>
   <summary>Configure additional workflows:</summary>

   [V1 Local RAG AI Agent](<http://localhost:5678/workflow/vTN9y2dLXqTiDfPT>)

   [V2 Qdrant RAG AI Agent](<http://localhost:5678/workflow/hrnPh6dXgIbGVzIk>)

   [V3 Local Agentic RAG AI Agent](<http://localhost:5678/workflow/RssROpqkXOm23GYL>)

   </details>  

6. Open <http://localhost:8080/> in your browser to set up Open WebUI.
   You’ll only have to do this once. You are NOT creating an account with Open
   WebUI in the setup here, it is only a local account for your instance!

7. Go to Workspace -> Functions -> New Function -> Function Name + Function ID +
   Function Description and copy then paste the code below to implement Cole
   Medin's n8n + OpenWebUI integration.  

   <details>
   <summary>N8N Pipe - n8n_pipe.py</summary>

    ```python
    """
    title: n8n Pipe Function
    author: Cole Medin
    author_url: https://www.youtube.com/@ColeMedin
    version: 0.2.0
    
    This module defines a Pipe class that utilizes N8N for an Agent
    """

    from typing import Optional, Callable, Awaitable
    from pydantic import BaseModel, Field
    import os
    import time
    import requests


    def extract_event_info(event_emitter) -> tuple[Optional[str], Optional[str]]:
        if not event_emitter or not event_emitter.__closure__:
            return None, None
        for cell in event_emitter.__closure__:
            if isinstance(request_info := cell.cell_contents, dict):
                chat_id = request_info.get("chat_id")
                message_id = request_info.get("message_id")
                return chat_id, message_id
        return None, None


    class Pipe:
        class Valves(BaseModel):
            n8n_url: str = Field(
                default="https://n8n.[your domain].com/webhook/[your webhook URL]"
            )
            n8n_bearer_token: str = Field(default="...")
            input_field: str = Field(default="chatInput")
            response_field: str = Field(default="output")
            emit_interval: float = Field(
                default=2.0, description="Interval in seconds between status emissions"
            )
            enable_status_indicator: bool = Field(
                default=True, description="Enable or disable status indicator emissions"
            )

        def __init__(self):
            self.type = "pipe"
            self.id = "n8n_pipe"
            self.name = "N8N Pipe"
            self.valves = self.Valves()
            self.last_emit_time = 0
            pass

        async def emit_status(
            self,
            __event_emitter__: Callable[[dict], Awaitable[None]],
            level: str,
            message: str,
            done: bool,
        ):
            current_time = time.time()
            if (
                __event_emitter__
                and self.valves.enable_status_indicator
                and (
                    current_time - self.last_emit_time >= 
                    self.valves.emit_interval or done
                )
            ):
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "status": "complete" if done else "in_progress",
                            "level": level,
                            "description": message,
                            "done": done,
                        },
                    }
                )
                self.last_emit_time = current_time
    
        async def pipe(
            self,
            body: dict,
            __user__: Optional[dict] = None,
            __event_emitter__: Callable[[dict], Awaitable[None]] = None,
            __event_call__: Callable[[dict], Awaitable[dict]] = None,
        ) -> Optional[dict]:
            await self.emit_status(
                __event_emitter__, "info", "/Calling N8N Workflow...", False
            )
            chat_id, _ = extract_event_info(__event_emitter__)
            messages = body.get("messages", [])

            # Verify a message is available
            if messages:
                question = messages[-1]["content"]
                try:
                    # Invoke N8N workflow
                    headers = {
                        "Authorization": f"Bearer {self.valves.n8n_bearer_token}",
                        "Content-Type": "application/json",
                    }
                    payload = {"sessionId": f"{chat_id}"}
                    payload[self.valves.input_field] = question
                    response = requests.post(
                        self.valves.n8n_url, json=payload, headers=headers
                    )
                    if response.status_code == 200:
                        n8n_response = response.json()[self.valves.response_field]
                    else:
                        raise Exception(f"Error: {response.status_code} - {response.text}")

                    # Set assitant message with chain reply
                    body["messages"].append({"role": "assistant", "content": n8n_response})
                except Exception as e:
                    await self.emit_status(
                        __event_emitter__,
                        "error",
                        f"Error during sequence execution: {str(e)}",
                        True,
                    )
                    return {"error": str(e)}
            # If no message is available alert user
            else:
                await self.emit_status(
                    __event_emitter__,
                    "error",
                    "No messages found in the request body",
                    True,
                )
                body["messages"].append(
                    {
                        "role": "assistant",
                        "content": "No messages found in the request body",
                    }
                )

            await self.emit_status(__event_emitter__, "info", "Complete", True)
            return n8n_response
    ```

    </details>

8. Copy the "Production" webhook URL from the workflow set in step 6.

9. Click on the gear icon and set the n8n_url to the production URL for the
webhook you copied in a previous step.

10. Toggle the function on and now it will be available in your model dropdown
in the top left.  

To open n8n, visit <http://localhost:5678/> in your browser.
To open Open WebUI, visit <http://localhost:3000/>.

With n8n, you have access to over 400 integrations and a suite of basic and
advanced AI nodes such as:
[AI Agent](https://docs.n8n.io/integrations/builtin/cluster-nodes/root-nodes/n8n-nodes-langchain.agent/),
[Text classifier](https://docs.n8n.io/integrations/builtin/cluster-nodes/root-nodes/n8n-nodes-langchain.text-classifier/),
and [Information Extractor](https://docs.n8n.io/integrations/builtin/cluster-nodes/root-nodes/n8n-nodes-langchain.information-extractor/)
nodes.  

To keep everything local, use the Ollama node for your language model and Qdrant
as your vector store.

> [!NOTE]
> AI-Suite is designed to help you get started with self-hosted AI
> workflows. While it is not fully optimized for production environments, it
> combines robust components that work well together for personal porjects.
> Of course, you can further customize it to meet your specific needs.

## Upgrading

To update all containers to their latest versions (n8n, Open WebUI, etc.),
run these commands:

```bash
# Stop all services
docker compose -p ai-suite -f docker-compose.yml --profile <your-profile> down

# Pull latest versions of all containers
docker compose -p ai-suite -f docker-compose.yml --profile <your-profile> pull

# Start services again with your desired profile
python start_services.py --profile <your-profile>
```

Replace `<your-profile>` with one: `cpu`, `gpu-nvidia`, `gpu-amd`, or `none`.

> [!NOTE]
> The `start_services.py` script itself does not update containers - it only
> restarts them or pulls them if you are downloading these containers for the
> first time. To get the latest versions, you must explicitly run the
> commands above.

## Troubleshooting

Here are solutions to common issues you might encounter:

### Supabase Issues

- **Supabase Pooler Restarting**: If the supabase-pooler container keeps
  restarting itself, follow the instructions in [this GitHub issue](https://github.com/supabase/supabase/issues/30210#issuecomment-2456955578).

- **Supabase Analytics Startup Failure**: If the supabase-analytics container
  fails to start after changing your Postgres password, delete the folder `supabase/docker/volumes/db/data`.

- **If using Docker Desktop**: Go into the Docker settings and make sure
  "Expose daemon on tcp://localhost:2375 without TLS" is turned on

- **Supabase Service Unavailable** - Make sure you don't have an "@" character
  in your Postgres password! If the connection to the kong container is working
  (the container logs say it is receiving requests from n8n) but n8n says it
  cannot connect, this is generally the problem from what the community has
  shared. Other characters might not be allowed too, the @ symbol is just the
  one I know for sure!

- **SearXNG Restarting**: If the SearXNG container keeps restarting, run the
  command "chmod 755 searxng" within the ai-suite folder so SearXNG has the
  permissions it needs to create the uwsgi.ini file.

- **Files not Found in Supabase Folder** - If you get any errors around files
missing in the supabase/ folder like .env, docker/docker-compose.yml, etc. This
most likely means you had a "bad" pull of the Supabase GitHub repository when
you ran the start_services.py script. Delete the supabase/ folder within the
Local AI Package folder entirely and try again.

### GPU Support Issues

- **Windows GPU Support**: If you're having trouble running Ollama with GPU
support on Windows with Docker Desktop:
  1. Open Docker Desktop settings
  2. Ensure 'Enable WSL2 backend' is enabled
  3. See the [Docker GPU documentation](https://docs.docker.com/desktop/features/gpu/)
  for more details

- **Linux GPU Support**: If you're having trouble running Ollama with GPU
support on Linux, follow the [Ollama Docker instructions](https://github.com/ollama/ollama/blob/main/docs/docker.md).

## 🛍️ More AI templates

For more AI workflow ideas, visit the [**official n8n AI template
gallery**](https://n8n.io/workflows/?categories=AI). From each workflow,
select the **Use workflow** button to automatically import the workflow into
your local n8n instance.

## 👓 Recommended reading

Useful content for deeper understanding AI concepts.

- [AI agents for developers: from theory to practice with n8n](https://blog.n8n.io/ai-agents/)
- [Tutorial: Build an AI workflow in n8n](https://docs.n8n.io/advanced-ai/intro-tutorial/)
- [Langchain Concepts in n8n](https://docs.n8n.io/advanced-ai/langchain/langchain-n8n/)
- [Demonstration of key differences between agents and chains](https://docs.n8n.io/advanced-ai/examples/agent-chain-comparison/)
- [What are vector databases?](https://docs.n8n.io/advanced-ai/examples/understand-vector-databases/)

## Tips & tricks

### Accessing local files

**AI-Suite** will create a `./shared` folder (by default, located in the
root directory) which is a _volume_ mounted to the n8n container and
allows n8n to access files on disk. This folder within the n8n container is
located at `/data/shared` -- this is the path you’ll need to use in nodes that
interact with the local filesystem.

### Nodes that interact with the local filesystem

- [Read/Write Files from Disk](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.filesreadwrite/)
- [Local File Trigger](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.localfiletrigger/)
- [Execute Command](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.executecommand/)

## 📜 License

This project (originally created by the n8n team, link at the top of the README)
is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for  
details.
