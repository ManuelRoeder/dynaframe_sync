# MidJourney Gallery Sync for Art Frames 

Python script that automatically fetches the latest images of the showcase area of Midjourney.
The images are obtained in full resolution.

NO MIDJOURNEY SUBSCRIPTION REQUIRED.

##Prerequisites:
Raspberry Pi 3B+ or better

Dynaframe v3 Pro image

Python 3+

Python package selenium

Chrome driver for Raspberry Pi

##Usage:
Run mj_sync.py to start the sync procedure.
Parameters are:
- path, the directory to sync the gallery files to. Should point to a location that is listed as DynaFrame playlist. Defaults to "/home/pi/Pictures/Midjourney"
- seconds, time in seconds between gallery updates. Defaults to 1h.
- headless, used for debugging. Defaults to True
- gallery, MJ gallery to fetch from: "top" or "recent". Defaults to "recent"
- show_prompts, Merge the text prompt into the image
- orientation, define the image aspect ratio to show: "portrait_only", "landscape_only", "all". Defaults to "portrait_only"

The sync is implemented to first check for, wipe and recreate the "path" directory. 
New images are added to the "path" dir from the given MJ gallery.
The script is sent to sleep mode for "seconds" seconds.
After the sleep timer expires a new scan checks the MJ gallery and only unseen images
are downloaded and added the the "path" folder.


##Permanent setup
First copy mj_sync.py to "/bin" directory.
Create a cronjob with

sudo crontab -e

Finally add the job to start the script 60 seconds after boot:

@reboot sleep 60 && /path/to/your/python /bin/mj_sync.py --gallery="hot" &

##Preview
Images with corresponding text prompts
![61511e6d-a0e6-4fae-8080-063a56d82695](https://user-images.githubusercontent.com/9356580/192499530-07d73299-ab72-4a66-a58c-b35518bc7e54.png)


![e3751829-978d-4f86-84bf-0127118c3c1e](https://user-images.githubusercontent.com/9356580/192499563-1b51840e-f9a0-4621-9797-389be02ff494.png)