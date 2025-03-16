Disaster Tracker Project
UI Basic Module README (Author Kyrylo Brener)

This module in current version is connected to calendarModule.

To run:
1) navigate to frontendModule folder
2) run python3 app.py 
NOTE: you might need venv to run it locally. install needed stuff for venv using requirements.txt file:
pip install -r requirements.txt
3) Navigate to http://localhost:5005/

If calendarModule is running on your local as well as rabbit mq instance, the system will work.

Usage:
1) Click on authorization button
2) Authorize via google on separate tab which will open automatically
3) Upon successful authorization you will see /calendar page on your origin tab
4) Select any dates and click on 'submit' button
5) Page will show you parsed events

