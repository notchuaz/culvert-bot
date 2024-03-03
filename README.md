# CulvertBot
CulvertBot is a bot for Discord servers (__currently only made for Saga's discord__) built on top of [interactions.py](https://interactions-py.github.io/interactions.py/). This bot is a semi-automatic culvert score tracker for Maplestory guilds. Utilizing PyTesseract, guild admins can use screenshots of their guild pages to log a guild member's name, class, level, and culvert score. Users can then query the bot for information on the guild's culvert scores.

# Features

### Admin-Only Commands
Only those with administrator priviledges or view audit log (willing to change this one) priviledges can use these commands. You can also set your own permissions by going into Server Settings -> Integrations -> Culvert Bot and overwrite the bot's permission's there for specific users or roles.

__Member-Based Commands__

* `/member add [name][class][discord]` -> Add a guild member to the database for the bot to crossreference and recognize.
    * __Usage:__ Use when a new member joins the guild.
* `/member remove [name]` -> Removes a guild member from the database.
    * __Usage:__ Use when a member leaves the guild.
* `/member update [name][name_update][class_update][discord_update][level_update]` -> Updates the name, class, level, or discord user ID.
    * __Usage:__ Use when a member changes any one of the aforementioned fields. Updating the level is mainly used to fix bot misinterpretation. Level tracking should normally be handled by the bot.
* `/member search [name]` -> Search for a member in the database by their name. This will return the basic information of the member.
    * __Usage:__ Use this if you need to check certain fields of a member or to see if they exist.
* `/member view` -> Returns the number of members logged and displays all the names of members in alphabetical order.
    * __Usage:__ Use this to compare the database to the current guild members

__Culvert-Based Commands__

* `/culvert update_all [culv_sc_(1-12)][date]` -> Upload 1 to 12 (depending on how many members your guild has) screenshots of the guild culvert page. You have the option to set a date for the log, otherwise it will be the current date in UTC at the time of running the command.
    * __Usage:__ The screenshot of the scores should ONLY ENCAPSULATE THE AREA AS SHOWN BELOW! Including any other pieces of text could cause the bot to misinterpret information and cause errors. __Currently, it is recommended that you save your screenshots (easiest to copy paste them into discord and then dragging them to your desktop) just in case there is a misinterpretation and the bot requests for a new set of screenshots.__ 
        ![culvert screenshot example](https://i.imgur.com/7OdK6Ko.png)
* `/culvert ping [culv_sc_(1-12)]` -> Upload 1 to 12 (depending on how many members your guild has) screenshots of the guild culvert page.
    *__Usage:__ The screenshots provided will be exactly the same as they appeared in `/culvert update_all`. This will then ping every person that currently has their discord registered and a current culvert score of 0.
* `/culvert update_one [name][date][score_update]` -> Updates the culvert score for one member at a specific date.
    * __Usage:__ Do this if there happened to be any changes to someone's culvert score or if it was read in incorrectly.
* `/culvert remove_all [date]` -> Removes the culvert scores for all members at a specific date.
    * __Usage:__ Use this if the bot misreads mass amounts of members or fails entirely and prepare to reupload screenshots.
* `/culvert remove_one [name][date]` -> Removes the culvert score for one member at a specific date.
    * __Usage:__ Similar to the previous command, except will only remove one entry.
* `/culvert add_one [name][date][score]` -> Adds a culvert score-date pair for a specified member.
    * __Usage:__ Use just in case a score needs to be added manually.
* `/culvert changes` -> Displays the top 5 members with the largest improvement from their previous PR this week.

### Public Commands
* `/saga [name]` -> Returns a generated graph and history of culvert scores for the specified member. The scores are sorted from most recent to earliest.
* `/saga [date]` -> Returns the logged culvert scores on a specified date sorted from highest to lowest.
* `/saga [class]` -> Returns the most recent culvert scores logged for a specific class.