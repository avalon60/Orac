<p align="center">
  <img src="assets/images/orac-logo.png" alt="Orac Logo" width="300" height="250">
</p>

<h1 align="center">Orac - Version 0.1.0</h1>

<p align="center">
  <em>Your retro-futuristic home AI assistant.</em>
</p>

<p align="center">
  <a href="https://github.com/Avalon60/orac">
    <img src="https://img.shields.io/badge/python-3.9%2B-blue.svg" alt="Python 3.9+">
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License">
  </a>
  <a href="https://github.com/Avalon60/orac/actions">
    <img src="https://img.shields.io/github/actions/workflow/status/Avalon60/orac/ci.yml?branch=main&label=build" alt="Build Status">
  </a>
</p>

---

## ✨ Features (currently a roadmap)

- 🎤 **Voice-Driven AI**: Natural language interaction via satellite Raspberry Pi units.  
- 🧠 **Conversational Intelligence**: Integrated with LM Studio for cutting-edge AI responses.  
- 🏠 **Smart Hub Control**: Manage lights, media, and IoT devices seamlessly.  
- 🧩 **Home Assistant Integrations**: Works hand-in-hand with Home Assistant for extensive smart home control.  
- 💬 **Client Chatbot**: Interact with Orac through a web or desktop chatbot interface.  
- 🌐 **Supports Multiple LLM Services**: Connects to LM Studio, Ollama, OpenAI, and more.  
- 🛠 **Modular Design**: Easily extend Orac with custom skills and automations.  
- 🖥 **Cross-Platform**: Works with Linux Mint and other major platforms.  
- 🔑 **Administered via APEX Web Console**: User and configuration management through Oracle APEX at [http://localhost:8042/ords/orac/f?p=1042:LOGIN](http://localhost:8042/ords/orac/f?p=1042:LOGIN).  

---

## 📂 Quick Links

- [Installation](#-installation)
- [Oracle Free Setup](#-oracle-free-setup)
- [APEX Administration](#-apex-administration)
- [Usage](#-usage)
- [License](#-license)

---

## 📦 Installation

Clone the repository and install Orac in editable mode:

```bash
git clone https://github.com/Avalon60/orac.git
cd orac
pip install -e .
````

*(Add any additional setup instructions here)*

---

## 🛢 Oracle Free Setup

Orac uses an Oracle Database for configuration and metadata storage. To get started:

### Install Oracle Free (23ai)

Follow Oracle’s instructions to install **Oracle Database Free**:

* [Download Oracle Free](https://www.oracle.com/database/free/)
* [Oracle Free Documentation](https://docs.oracle.com/en/database/oracle/oracle-database/23/)

Alternatively, you can use a **Docker container** for local development:

```bash
docker run -d \
  -p 1521:1521 -p 5500:5500 \
  --name oracle-free \
  container-registry.oracle.com/database/free:23.5.0
```

* The default container uses:

  * **Username**: `system`
  * **Password**: `oracle`
  * **Service Name**: `FREEPDB1`

> ⚠️ *Change credentials for production use.*

---

### Create Orac User & Schema

Log in and create a dedicated user for Orac:

```sql
CREATE USER orac IDENTIFIED BY orac_password;
GRANT CONNECT, RESOURCE TO orac;
```

> ⚠️ Adjust roles/permissions as needed.

---

## 🧭 APEX Administration

Orac’s user-management and configuration functions are handled through the **Orac Admin APEX application**, which provides a browser-based interface for maintaining users, skills, and system settings.

Once your Oracle Free / ORDS stack is running, open the Orac Admin app in a browser:

```
http://localhost:8042/ords/f?p=1042:LOGIN
```

This URL launches the **Orac Administration Application** login page.

### Default Workspace and Credentials

| Setting       | Value                  | Notes                                                       |
| ------------- | ---------------------- | ----------------------------------------------------------- |
| **Workspace** | `ORAC`                 | APEX workspace associated with the Orac schema.             |
| **Username**  | `ORAC_ADMIN`           | The initial administrative account.                         |
| **Password**  | *(set on first login)* | You’ll be prompted to choose a password at initial sign-in. |

After first login, you can use the APEX interface to manage user accounts, roles, permissions, and configuration data.

> 💡 *This application provides everyday administration of Orac — including user setup, role management, and configuration — with no command-line access required.*

> 🧰 *Developers who need to access the underlying APEX workspace can still do so via:*
> [http://localhost:8042/ords/r/apex/workspace-sign-in/oracle-apex-sign-in](http://localhost:8042/ords/r/apex/workspace-sign-in/oracle-apex-sign-in)

> 🌍 *If accessing from another machine or container, replace `localhost` in the URL with your host’s IP address or hostname (e.g., `http://192.168.0.42:8042/ords/f?p=1042:LOGIN`).*

---

### 🧩 Troubleshooting APEX Login

If you cannot access the Orac Admin application:

1. **Verify ORDS is running:**
   Check your container logs or terminal output — you should see a line like:

   ```
   INFO  ORDS has started and is listening on port 8042
   ```

2. **Check the URL:**
   Ensure the URL path ends with `f?p=1042:LOGIN` (not the developer workspace path).

3. **Confirm port mapping (Docker):**
   If running in a container, make sure port **8042** on the host maps to **8042** in the container:

   ```bash
   docker ps
   ```

   Look for `0.0.0.0:8042->8042/tcp`.

4. **Clear browser cache or use incognito mode:**
   Cached session tokens sometimes prevent APEX login pages from loading correctly.

5. **Reset ORAC_ADMIN password (if forgotten):**
   Connect via SQL*Plus or SQLcl:

   ```sql
   ALTER USER ORAC_ADMIN IDENTIFIED BY new_password;
   ```

6. **Check APEX version / installation:**
   If the login page still fails to load, confirm that APEX is properly installed and configured in the PDB:

   ```sql
   SELECT version FROM apex_release;
   ```

> 🧠 *Tip: If the APEX listener doesn’t respond, restart the ORDS service or your container — it usually resolves transient startup timing issues.*

---

## 🛠 Usage

Start Orac with:

```bash
python -m orac
```

*(Describe how to configure Raspberry Pi satellites and connect to your home network.)*

---

## Checking the Install
In the event of any problems after the òracledb-init.sh`is complete, you should open a terminal and run the command:    

`docker logs orac-db`

Also, to monitor this during the install, you can use something like:   

`docker logs --tail 200 -f orac-db`

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🤖 About the Name

The name **Orac** pays homage to the iconic AI from *Blake’s 7*—a nod to retro science fiction with modern AI innovation.

---

<p align="center">
  <em>"Logic is a wreath of pretty flowers which smell bad."</em>
</p>
