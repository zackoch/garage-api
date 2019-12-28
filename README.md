# garage-api
Python API for automating remote start and garage door.

Note: this is highly specific and should only be used as an example for your own project. Assumptions have been made that you at least know your way around an RPI and Linux. Basic hardware knowledge is needed (you need pin headers to plug a wire into it, Etc.)

# Danger!
This system does not check to see if the door is open prior to allowing the car to start. I purposefully made it this way so the car could be started when it is in the driveway without having to have the door open. <b>My implementation of this automation to start the car is done in a different tool (Home Assistant) and DOES perform a check to ensure the garage is open before allowing the car to start.</b>

Be aware - Carbon Monoxide <b>will</b> kill you. Use your head.

# Hardware
- Raspberry Pi Zero W (with headers)
- 2-Channel 5VDC relay
- Spare remote start fob/remote
- Garage door opener, or an extra fob/remote

# Pre-requisites
1. Load your Raspberry Pi with Raspbian.
2. Take apart your spare car starter remote and solder wires to the switch contacts so that you can short the switch simulating a button press.
3. Run wires to your garage door opener's main switch, or solder wires to a spare remote. If your garage door has a physical switch you can follow the wires to the opener to see where the main switch terminals are. Shorting these will actuate the door.

# Wiring the Raspberry Pi
For pin numbering we will be using the Broadcom numbering system within the program itself - be warned.

Pins used:
<table>
  <tr>
    <th>Board Pin Location</th>
    <th>BCM Pin Number</th>
    <th>Description</th>
  </tr>
  <tr>
    <td>2</td>
    <td>5v Power</td>
    <td>5v power source for powering the relay</td>
  </tr>
  <tr>
    <td>11</td>
    <td>BCM 17</td>
    <td>Remote start signal pin (goes to relay)</td>
  </tr>
  <tr>
    <td>13</td>
    <td>BCM 27</td>
    <td>Garage signal pin (goes to relay)</td>
  </tr>
    <tr>
    <td>31</td>
    <td>BCM 6</td>
    <td>Input pin for reed switch (goes to Normally closed on reed switch)</td>
  </tr>
  <tr>
    <td>6</td>
    <td>Ground</td>
    <td>Ground pin (goes to relay)</td>
  </tr>
    <tr>
    <td>39</td>
    <td>Ground</td>
    <td>Ground pin (goes COM on reed switch)</td>
  </tr>
</table>

Ensure the signal pins for the garage door and remote start go to the proper relay channels. 

Here's a very bad wiring diagram:

![alt text](https://i.imgur.com/Ax3Szqg.jpg "super shitty wiring diagram")
  
# Configuring Linux
#h2 Basics
SSH to the RPI

Change the default password
```shell
passwd pi
```
Note it's IP address (write it down or something)
```
ifconfig -a
```
Update sources
```
sudo apt-get upgrade
```
Upgrade packages
```
sudo apt-get upgrade -y
```
Install required resources
```
sudo apt-get -y install python3 python3-venv python-dev supervisor nginx git uuid-runtime
```
Ensure you're in pi's home directory (`cd ~`) and clone this repo
```
git clone https://github.com/zackoch/garage-api
```
cd into garage-api
```
cd garage-api
```
Create a virtual environment with python3 and get into it
```
python3 -m venv venv
source venv/bin/activate
```
Install python dependencies 
```
pip install -r requirements.txt
```
Generate a UUID to use as an your API key (returns something like `05f6bf62-879f-444c-9116-169f34655916`)
```
uuidgen
```
Edit the config_sample.json file and paste your API key in between the quotes where the sample one is shown (replace it).

If you didn't use the pins in the shitty wiring diagram above, change them here. Ensure you use BCM pin numbering or you'll have a bad time.

<b>Important</b>
- under car, change the pulse value to the number of seconds you must hold your remote start button down to start your car
- under garage, change the time value to the number of seconds it takes your garage to fully open when you press the button (to be safe measure the amount of time required to open and close and put the higher value here...)

```
nano config_sample.json
```
```
{
  "api_key": "05f6bf62-879f-444c-9116-169f34655916",
  "car": {
    "pin": 17,
    "pulse": 2
  },
  "garage": {
    "pin": 27,
    "pulse": 0.5,
    "state_pin": 6,
    "time": 15
  }
}
```
Rename the config_sample.json to config.json
```
mv config_sample.json config.json
```
Add environment variable for FLASK_APP (you'll need to close your SSH session and re-open it for it to take effect)
```
echo "export FLASK_APP=app.py" >> ~/.profile
```
# Daemon configuration
Create a supervisor config
```
sudo nano /etc/supervisor/conf.d/app.conf
```
Paste in the following - remember when I said to write down your pi's IP address? I bet you didn't listen. You'll want to replace the one in the example below with whatever yours is...
```
[program:app]
command=/home/pi/garage-api/venv/bin/gunicorn -b 192.168.1.202:8000 -w 4 app:app
directory=/home/pi/garage-api
user=pi
autostart=true
autorestart=true
stopasgroup=true
killasgroup=true
```
Restart supervisorctl
```
sudo supervisorctl reload
```
# Nginx (webserver) configuration
The following will create a self-signed cert... you should probably get a free one through lets-encrypt.
```
cd ~
mkdir certs
openssl req -new -newkey rsa:4096 -days 365 -nodes -x509 -keyout certs/key.pem -out certs/cert.pem
```
Remove default nginx site
```
sudo rm -f /etc/nginx/sites-available/default
```
Create a new virtual host
```
sudo nano /etc/nginx/sites-available/app
```
Add the following code to that file and save it
```
server {
    listen 443 ssl;
    server_name _;

    ssl_certificate /home/pi/certs/cert.pem;
    ssl_certificate_key /home/pi/certs/key.pem;
    access_log /var/log/app_access.log;
    error_log /var/log/app_error.log;

    location / {
        proxy_pass http://localhost:8000;
        proxy_redirect off;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```
Link server blocks and make nginx start on boot, and restart nginx
```
sudo ln -s /etc/nginx/sites-available/app /etc/nginx/sites-enabled/
sudo systemctl enable nginx
sudo systemctl restart nginx
```
# Now what?
Start the api
```
sudo supervisorctl restart all
```
Give it 15 seconds or so, and it will be ready to start receiving requests... You could integrate this into a frontend, smart home controller, or whatever your heart desires. If you just want to test it, download the Insomnia rest client and start sending it requests.

<b>Note: ensure your API key is in a header on every request like the one shown in the screenshot below</b>
![alt-text](https://i.imgur.com/2wMd8Hh.png "auth")


`GET: https://yourip/car` - returns the last time it was started, and the clients IP

`GET: https://yourip/garage` - returns the last garage desired action, time, client ip, and actual state it is in

`POST https://yourip/car?action=start` - starts your car - will return 200 with some simple JSON

`POST https://yourip/garage?action=open` - opens your garage - will return 200 with some simple JSON. <b>Note: it will take whatever time you set as your time variable in the config.json file before it responds - this is so it captures the final state it's in and responds with it in it's response.</b>

`POST https://yourip/garage?action=close` - opens your garage - will return 200 with some simple JSON. <b>Note: it will take whatever time you set as your time variable in the config.json file before it responds - this is so it captures the final state it's in and responds with it in it's response.</b>
  
# Todo
* create an endpoint to get live status of garage reed switch
* learn how to program better









