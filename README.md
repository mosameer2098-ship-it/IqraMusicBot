<h3 align="center">
      ─「 <\> Deploy On Heroku <\> 」─
</h3>

<p align="center"><a href="https://dashboard.heroku.com/new?template=https://github.com/mosameer2098-ship-it/IqraMusicBot"> <img src="https://img.shields.io/badge/Deploy%20On%20Heroku-black?style=for-the-badge&logo=heroku" width="220" height="38.45"/></a></p>


### 🔧 Quick Setup

1. **Upgrade & Update:**
   ```bash
   sudo apt-get update && sudo apt-get upgrade -y
   ```

2. **Install Required Packages:**
   ```bash
   sudo apt-get install python3-pip ffmpeg -y
   ```
3. **Setting up PIP**
   ```bash
   sudo pip3 install -U pip
   ```
4. **Installing Node**
   ```bash
   curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.38.0/install.sh | bash && source ~/.bashrc && nvm install v18
   ```
5. **Clone the Repository**
   ```bash
   git clone https://github.com/ARYANSONIOP/TestingMusicRepo && cd TestingMusicRepo
   ```
6. **Install Requirements**
   ```bash
   pip3 install -U -r requirements.txt
   ```
7. **Create .env  with sample.env**
   ```bash
   cp sample.env .env
   ```
   - Edit .env with your vars
8. **Editing Vars:**
   ```bash
   vi .env
   ```
   - Press `I` Button On Keyboard To Start Editing.
   - Edit .env With Your Values.
   - Press `Ctrl + C`  Once You Are Done With Editing Vars And Type `:wq` To Save .env Or `:qa` To Exit Editing.
10. **Installing tmux**
    ```bash
    sudo apt install tmux -y && tmux
    ```
11. **Run The Bot**
    ```bash
    bash start
    ```

