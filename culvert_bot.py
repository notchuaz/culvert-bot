import os
import io
import certifi
import math
import json
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from dotenv import load_dotenv
from interactions import Client, Intents, OptionType, Embed, File, Permissions, SlashContext, SlashCommand, SlashCommandOption, listen, slash_default_member_permission
from interactions.ext.paginators import Paginator
from culvert_processor import get_culvert_scores
from culvert_name_matcher import link_names
from openai_generator import story_generator
from pymongo.mongo_client import MongoClient
from datetime import datetime
from PIL import Image

def plot_to_image(x, y):
    fig, ax = plt.subplots()
    ax.plot(x, y, marker='o', color='#3290d0')
    ax.set_xlabel("Date", color='#e1e1e0')
    ax.set_ylabel("Score", color='#e1e1e0')
    ax.set_facecolor('#222222')
    fig.patch.set_facecolor('#222222')
    spine_color = '#e1e1e0'
    for spine in ax.spines.values():
        spine.set_edgecolor(spine_color)
    ax.tick_params(colors=spine_color, which='both')
    ax.set_xticklabels([])
    max_y = max(y)
    max_x = x[y.index(max_y)]
    ax.annotate(f'{max_y}',
                (max_x, max_y),
                textcoords="offset points",
                xytext=(0,10),
                ha='center',
                color='#e1e1e0',
                bbox=dict(facecolor='black', alpha=0.5, edgecolor='white', boxstyle='round,pad=0.5'))
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format='png')
    buf.seek(0)
    plt.close(fig)

    return buf

def bytesio_to_image(buf):
    image = Image.open(buf)
    return image

def create_embed(title, description="", color="", author="", thumbnail="", footer="", field=""):
    embed = Embed(title=title, description=description, color=color)
    if author:
        embed.set_author(author)
    if thumbnail:
        embed.set_thumbnail(url=thumbnail)
    if footer:
        embed.set_footer(footer)
    if field:
        for item in field:
            embed.add_field(name=item["name"], value=item["value"], inline=item["inline"])  
    return embed

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
URI = os.getenv('APP_URI')

with open("embed_thumbnails.json", "r") as file:
    embed_thumbnails = json.load(file)

db_client = MongoClient(URI, tlsCAFile=certifi.where())
try:
    db_client.admin.command('ping')
    print("Connected to MongoDB.")
except Exception as e:
    print(e)

db_culvert = db_client['culvert-score-database']
collection_scores = db_culvert['player-scores']
collection_names = db_culvert['player-names']

bot = Client(intents=Intents.DEFAULT)
member_cmd = SlashCommand(name="member", description="Add, remove, update, or search members in the database.", default_member_permissions=Permissions.ADMINISTRATOR)
culvert_cmd = SlashCommand(name="culvert", description="Update, remove, or change culvert scores for members.", default_member_permissions=Permissions.ADMINISTRATOR, scopes=[1162977790832955432])
search_cmd = SlashCommand(name="saga", description="Search the database by member, date, or class for culvert scores.")

@listen()
async def on_ready():
    print("Ready to go!")
    print(f"This bot is owned by {bot.owner}")

# @base_cmd.subcommand(sub_cmd_name="clear", sub_cmd_description="Clears the database. DEV USE ONLY!")
# async def clear(ctx: SlashContext):
#     collection_scores.delete_many({})
#     await ctx.send("Cleared score database.")

@member_cmd.subcommand(
    sub_cmd_name="add", 
    sub_cmd_description="Add guild members for the bot to recognize.",
    options=[
        SlashCommandOption(
            name="guild_member",
            description="Name of guild member. Treat special characters as base characters.",
            required=True,
            type=OptionType.STRING
        ),
        SlashCommandOption(
            name="guild_member_class",
            description="Class of the guild member. Enter as it would appear on the guild page, i.e., Arch Mage (F/P).",
            required=True,
            type=OptionType.STRING
         ),
        SlashCommandOption(
            name="guild_member_discord",
            description="The discord ID of the member.",
            required=False,
            type=OptionType.STRING
        )
    ]
)
async def add_member(ctx: SlashContext, guild_member: str, guild_member_class: str, guild_member_discord: str=None):  
    if collection_names.find_one({"name_lower": guild_member.lower()}) is None:
        member_discord_id = guild_member_discord if guild_member_discord else None
        member_data = {"name": guild_member.strip(), "class": guild_member_class.lower().strip(), "discord_id": member_discord_id, "name_lower": guild_member.strip().lower()}
        collection_names.insert_one(member_data)

        title_success = 'Add successful.'
        color_success = '#2bff00'
        thumbnail_success = embed_thumbnails["sugar_done"]
        fields_success = [
            {
                "name": "Name",
                "value": guild_member,
                "inline": False
            },
            {
                "name": "Class",
                "value": guild_member_class,
                "inline": False
            },
            {
                "name": "Discord ID",
                "value": guild_member_discord,
                "inline": False
            }
        ]
        embed_success = create_embed(title_success, color=color_success, thumbnail=thumbnail_success, field=fields_success)  
        await ctx.send(embed=embed_success)
    else:
        title_failure = 'Unable to add.'
        description_failure = f'The name "{guild_member}" already exists. Maybe try updating it?'
        color_failure = '#FF0000'
        thumbnail_failure = embed_thumbnails["sugar_fail"]
        embed_failure = create_embed(title_failure, description=description_failure, color=color_failure, thumbnail=thumbnail_failure)
        await ctx.send(embed=embed_failure)

@member_cmd.subcommand(
    sub_cmd_name="remove", 
    sub_cmd_description="Remove guild member.",
    options=[
        SlashCommandOption(
            name="guild_member",
            description="Name of guild member. Treat special characters as base characters.",
            required=True,
            type=OptionType.STRING
        )
    ]
)
async def remove_member(ctx: SlashContext, guild_member: str):
    query = {"name_lower": guild_member.lower()}
    member = collection_names.find_one(query)
    if member:
        removed_member = collection_names.delete_one(query)
        removed_member_scores = collection_scores.delete_one({"name": guild_member.lower()})
        if removed_member.deleted_count == 1 and removed_member_scores.deleted_count == 1:
            title_success = 'Removal successful.'
            description_success = f'Successfully removed {guild_member}.'
            color_success = '#2bff00'
            thumbnail_success = embed_thumbnails["sugar_done"]
            embed_success = create_embed(title_success, color=color_success, description=description_success, thumbnail=thumbnail_success)
            await ctx.send(embed=embed_success)
    else:
        title_failure = 'Unable to remove.'
        description_failure = f'The name "{guild_member}" doesn\'t exist.'
        color_failure = '#FF0000'
        thumbnail_failure = embed_thumbnails["sugar_fail"]
        embed_failure = create_embed(title_failure, description=description_failure, color=color_failure, thumbnail=thumbnail_failure)
        await ctx.send(embed=embed_failure)

@member_cmd.subcommand(
    sub_cmd_name="update", 
    sub_cmd_description="Update guild member information.",
    options=[
        SlashCommandOption(
            name="guild_member",
            description="Name of guild member. Treat special characters as base characters.",
            required=True,
            type=OptionType.STRING
        ),
        SlashCommandOption(
            name="guild_member_updated",
            description="Updated member name. Treat special characters as base characters.",
            required=False,
            type=OptionType.STRING
        ),
        SlashCommandOption(
            name="guild_member_class_updated",
            description="Updated member class. Enter as it would appear on the guild page, i.e., Arch Mage (F/P).",
            required=False,
            type=OptionType.STRING
        ),
        SlashCommandOption(
            name="discord_updated",
            description="Updated member discord ID.",
            required=False,
            type=OptionType.STRING
        ),
        SlashCommandOption(
            name="level_updated",
            description="Updated member level. Can only be changed if culvert scores have been updated for this member.",
            required=False,
            type=OptionType.INTEGER
        )
    ]
)
async def update_member(ctx: SlashContext, guild_member: str, guild_member_updated: str=None, class_updated: str=None, discord_updated: str=None, level_updated: int=None):  
    query = {"name_lower": guild_member.lower()}
    member = collection_names.find_one(query)
    if member:
        member_name = guild_member_updated if guild_member_updated else member["name"]
        member_class = class_updated if class_updated else member["class"]
        member_discord_id = discord_updated if discord_updated else member["discord_id"]
        member_data = {"$set": 
                        {
                            "name": member_name.strip(), 
                            "class": member_class.lower().strip(), 
                            "discord_id": member_discord_id,
                            "name_lower": member_name.strip().lower()
                        }
                    }
        updated_member = collection_names.update_one(query, member_data)
        if updated_member.matched_count:
            title_success = 'Update successful.'
            color_success = '#2bff00'
            thumbnail_success = embed_thumbnails["sugar_done"]
            fields_success = [
                {
                    "name": "Name",
                    "value": member_name,
                    "inline": False
                },
                {
                    "name": "Class",
                    "value": member_class,
                    "inline": False
                },
                {
                    "name": "Discord ID",
                    "value": member_discord_id,
                    "inline": False
                }
            ]
            embed_success = create_embed(title_success, color=color_success, thumbnail=thumbnail_success, field=fields_success)  
            await ctx.send(embed=embed_success)
        query_scores = {"name": guild_member.lower()}
        member_scores = collection_scores.find_one(query_scores)
        if member_scores:
            member_level = level_updated if level_updated else member_scores["level"]
            scores_data = {"$set": 
                    {
                        "name": member_name.lower().strip(), 
                        "class": member_class.lower().strip(), 
                        "level": member_level
                    }
                }
            updated_member = collection_scores.update_one(query_scores, scores_data)
    else:
        title_failure = 'Unable to update.'
        description_failure = f'The name "{guild_member}" doesn\'t exist.'
        color_failure = '#FF0000'
        thumbnail_failure = embed_thumbnails["sugar_fail"]
        embed_failure = create_embed(title_failure, description=description_failure, color=color_failure, thumbnail=thumbnail_failure)
        await ctx.send(embed=embed_failure)
        return -1
    
@member_cmd.subcommand(
    sub_cmd_name="search", 
    sub_cmd_description="Search for member name.",
    options=[
        SlashCommandOption(
            name="guild_member",
            description="Name of guild member. Treat special characters as base characters.",
            required=True,
            type=OptionType.STRING
        )
    ]
)
async def search_member(ctx: SlashContext, guild_member: str):
    query = {"name_lower": guild_member.lower()}
    member = collection_names.find_one(query)
    if member:
        title_success = 'Member exists.'
        color_success = '#2bff00'
        thumbnail_success = embed_thumbnails["sugar_done"]
        fields_success = [
            {
                "name": "Name",
                "value": member["name"],
                "inline": False
            },
            {
                "name": "Class",
                "value": member["class"],
                "inline": False
            },
            {
                "name": "Discord ID",
                "value": member["discord_id"],
                "inline": False
            },
            {
                "name": "Name (normalized)",
                "value": member["name_lower"],
                "inline": False
            }
        ]
        embed_success = create_embed(title_success, color=color_success, thumbnail=thumbnail_success, field=fields_success)  
        await ctx.send(embed=embed_success)
    else:
        title_failure = 'Member does not exist.'
        description_failure = f'The name "{guild_member}" doesn\'t exist.'
        color_failure = '#FF0000'
        thumbnail_failure = embed_thumbnails["sugar_fail"]
        embed_failure = Embed(title_failure, color=color_failure, thumbnail=thumbnail_failure)
        await ctx.send(embed=embed_failure)
        return -1

@culvert_cmd.subcommand(
    sub_cmd_name="update_all", 
    sub_cmd_description="Updates the database with the culvert scores provided.",
    options=[
        SlashCommandOption(
            name="culv_sc_1",
            description="Culvert screenshot.",
            required=True,
            type=OptionType.ATTACHMENT
        ),
        SlashCommandOption(
            name="culv_sc_2",
            description="Culvert screenshot.",
            required=False,
            type=OptionType.ATTACHMENT
        ),
        SlashCommandOption(
            name="culv_sc_3",
            description="Culvert screenshot.",
            required=False,
            type=OptionType.ATTACHMENT
        ),
        SlashCommandOption(
            name="culv_sc_4",
            description="Culvert screenshot.",
            required=False,
            type=OptionType.ATTACHMENT
        ),
        SlashCommandOption(
            name="culv_sc_5",
            description="Culvert screenshot.",
            required=False,
            type=OptionType.ATTACHMENT
        ),
        SlashCommandOption(
            name="culv_sc_6",
            description="Culvert screenshot.",
            required=False,
            type=OptionType.ATTACHMENT
        ),
        SlashCommandOption(
            name="culv_sc_7",
            description="Culvert screenshot.",
            required=False,
            type=OptionType.ATTACHMENT
        ),
        SlashCommandOption(
            name="culv_sc_8",
            description="Culvert screenshot.",
            required=False,
            type=OptionType.ATTACHMENT
        ),
        SlashCommandOption(
            name="culv_sc_9",
            description="Culvert screenshot.",
            required=False,
            type=OptionType.ATTACHMENT
        ),
        SlashCommandOption(
            name="culv_sc_10",
            description="Culvert screenshot.",
            required=False,
            type=OptionType.ATTACHMENT
        ),
        SlashCommandOption(
            name="culv_sc_11",
            description="Culvert screenshot.",
            required=False,
            type=OptionType.ATTACHMENT
        ),
        SlashCommandOption(
            name="culv_sc_12",
            description="Culvert screenshot.",
            required=False,
            type=OptionType.ATTACHMENT
        ),
        SlashCommandOption(
            name="specified_date",
            description="Specify the date of entry if today's date is not when these scores were logged.",
            required=False,
            type=OptionType.STRING
        )
    ]
)
async def updateAll(
    ctx: SlashContext, 
    culv_sc_1: OptionType.ATTACHMENT,         
    culv_sc_2: OptionType.ATTACHMENT = None,  
    culv_sc_3: OptionType.ATTACHMENT = None,  
    culv_sc_4: OptionType.ATTACHMENT = None,     
    culv_sc_5: OptionType.ATTACHMENT = None,     
    culv_sc_6: OptionType.ATTACHMENT = None,     
    culv_sc_7: OptionType.ATTACHMENT = None,     
    culv_sc_8: OptionType.ATTACHMENT = None,     
    culv_sc_9: OptionType.ATTACHMENT = None,     
    culv_sc_10: OptionType.ATTACHMENT = None,    
    culv_sc_11: OptionType.ATTACHMENT = None,    
    culv_sc_12: OptionType.ATTACHMENT = None,
    specified_date: OptionType.STRING = None,):   
    def is_valid_date(date_str):
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
            return True
        except ValueError:
            return False
    
    if specified_date:
        if not is_valid_date(specified_date):
            title_fail = 'Date is invalid.'
            description_fail = 'Enter the date in this format: YYYY-MM-DD.'
            color_fail = '#FF0000'
            thumbnail_fail = embed_thumbnails["sugar_fail"]
            embed_fail = create_embed(title_fail, description=description_fail, color=color_fail, thumbnail=thumbnail_fail)
            await ctx.send(embed=embed_fail)
            return -1

    culvert_data = []
    player_name_data = collection_names.find({}, {"name": 1, "class": 1})
    player_name_list = [{"name": doc["name"], "class": doc["class"]} for doc in player_name_data]

    title_update = "Reading your culvert scores!"
    description_update = "This could take up to 30 seconds."
    color_update = "#FF9900"
    thumbnail_update = embed_thumbnails["sugar_inprogress"]
    embed_update = create_embed(title_update, color=color_update, description=description_update, thumbnail=thumbnail_update)
    embed_update_message = await ctx.send(embed=embed_update)

    for index in range(1, 13):
        culv_sc_var = f'culv_sc_{index}'
        culv_sc_img = locals().get(culv_sc_var)
        if culv_sc_img is not None:
            image_url = culv_sc_img.url
            culv_sc_read = get_culvert_scores(image_url)
            if culv_sc_read:
                culvert_data.extend(get_culvert_scores(image_url))
            else:
                title_screenshot_mess = 'Messy Screenshot!'
                description_screenshot_mess = f'Screenshot #{index} might be messy. Try changing the area of which you take the screenshot.'
                color_screenshot_mess = '#FF0000'
                thumbnail_screenshot_mess = embed_thumbnails["sugar_fail"]
                embed_screenshot_mess = create_embed(title_screenshot_mess, description=description_screenshot_mess, color=color_screenshot_mess, thumbnail=thumbnail_screenshot_mess)
                await embed_update_message.edit(embed=embed_screenshot_mess)
                return -1
    names_flat = [sublist[0] for sublist in culvert_data if sublist]
    if len(names_flat) != len(set(names_flat)):
        title_duplicate_entry = 'Duplicate Entry!'
        description_duplicate_entry = 'Did you accidentally upload the same screenshot twice? There appears to be at least 2 entries of the same culvert score.'
        color_duplicate_entry = '#FF0000'
        thumbnail_duplicate_entry = embed_thumbnails["sugar_fail"]
        embed_duplicate_entry = create_embed(title_duplicate_entry, description=description_duplicate_entry, color=color_duplicate_entry, thumbnail=thumbnail_duplicate_entry)
        await embed_update_message.edit(embed=embed_duplicate_entry)
    elif len(culvert_data) != collection_names.count_documents({}):
        title_member_mismatch = 'Member mismatch!'
        description_member_mismatch = 'The number of guild members currently logged and the number of culvert scores read are not equal! Check to see if all your guild members are accounted for! Also make sure that your screenshots capture the whole culvert page! \n\n Use /cb member [add, remove, update, search] commands to help!'
        color_member_mismatch = '#FF0000'
        thumbnail_member_mismatch = embed_thumbnails["sugar_fail"]
        fields_member_mismatch = [
            {
                "name": "# of Culvert Scores Read",
                "value": len(culvert_data),
                "inline": True
            },
            {
                "name": "# of Guild Members Logged",
                "value": collection_names.count_documents({}),
                "inline": True
            }
        ]
        embed_member_mismatch = create_embed(title_member_mismatch, description=description_member_mismatch, color=color_member_mismatch, thumbnail=thumbnail_member_mismatch, field=fields_member_mismatch)
        await embed_update_message.edit(embed=embed_member_mismatch)
    else:
        linked_names = link_names(culvert_data, player_name_list)

        for entry in linked_names:
            query = {"name": entry[1].lower()}
            scores_doc = collection_scores.find_one(query)
            if scores_doc:
                date_to_add = entry[2][4] if not specified_date else specified_date
                result = collection_scores.update_one(
                    {"name": entry[1].lower()},
                    {
                        "$push": {
                            "score": entry[2][3],
                            "date": date_to_add
                        },
                        "$set": {
                            "level": entry[2][2]
                        }
                    }
                )
            else:
                result = collection_scores.insert_one(
                    {
                        "name": entry[1].lower(),
                        "class": entry[2][1],
                        "level": entry[2][2],
                        "score": [entry[2][3]],
                        "date": [date_to_add]
                    }
                )
        title_success = "Culvert scores read and logged!"
        color_success = "#2BFF00"
        thumbnail_success = embed_thumbnails["sugar_done"]
        embed_success = create_embed(title_success, color=color_success, thumbnail=thumbnail_success)
        await embed_update_message.edit(embed=embed_success)

@culvert_cmd.subcommand(
    sub_cmd_name="update_one",
    sub_cmd_description="Edit the values of one member.",
    options=[
        SlashCommandOption(
            name="guild_member",
            description="Guild member's IGN.",
            required=True,
            type=OptionType.STRING
        ),
        SlashCommandOption(
            name="date",
            description="The date of the culvert score to update. Format: YYYY-MM-DD",
            required=True,
            type=OptionType.STRING
        ),
        SlashCommandOption(
            name="score_updated",
            description="New culvert score to update.",
            required=True,
            type=OptionType.INTEGER
        )
    ]
)
async def updateOne(ctx: SlashContext, guild_member: str, date: str, score_updated: int):
    def is_valid_date(date_str):
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
            return True
        except ValueError:
            return False
        
    if not is_valid_date(date):
        title_fail = 'Date is invalid.'
        description_fail = 'Enter the date in this format: YYYY-MM-DD.'
        color_fail = '#FF0000'
        thumbnail_fail = embed_thumbnails["sugar_fail"]
        embed_fail = create_embed(title_fail, description=description_fail, color=color_fail, thumbnail=thumbnail_fail)
        await ctx.send(embed=embed_fail)
        return -1

    query = {"name": guild_member.lower()}
    member = collection_scores.find_one(query)
    if member:
        if date in member["date"]:
            index = member["date"].index(date)
            update = {"$set":
                        {
                            f"score.{index}": score_updated
                        }
                    }
            member_updated = collection_scores.update_one(query, update)
            if member_updated.matched_count:
                member = collection_scores.find_one(query)
                title_success = 'Update successful.'
                color_success = '#2bff00'
                thumbnail_success = embed_thumbnails["sugar_done"]
                fields_success = [
                    {
                        "name": "Name",
                        "value": member["name"],
                        "inline": True
                    },
                    {
                        "name": "Date",
                        "value": member["date"][index],
                        "inline": True
                    },
                    {
                        "name": "Score",
                        "value": member["score"][index],
                        "inline": True
                    }
                ]
                embed_success = create_embed(title_success, color=color_success, thumbnail=thumbnail_success, field=fields_success)  
                await ctx.send(embed=embed_success)
            else:
                title_error = "Failed to update member."
                color_error = "#FF0000"
                thumbnail_error = embed_thumbnails["sugar_fail"]
                embed_error = create_embed(title_error, color=color_error, thumbnail=thumbnail_error)
                await ctx.send(embed=embed_error)
        else:
            title_error = "Unable to find date!"
            description_error = f"The date, {date}, has no log for {guild_member}."
            color_error = "#FF0000"
            thumbnail_error = embed_thumbnails["sugar_fail"]
            embed_error = create_embed(title_error, color=color_error, description=description_error, thumbnail=thumbnail_error)
            await ctx.send(embed=embed_error)
    else:
        title_error = "Member does not exist."
        description_error = f"The member, {guild_member}, does not exist."
        color_error = "#FF0000"
        thumbnail_error = embed_thumbnails["sugar_fail"]
        embed_error = create_embed(title_error, color=color_error, thumbnail=thumbnail_error, description=description_error)
        await ctx.send(embed=embed_error)

@culvert_cmd.subcommand(
    sub_cmd_name="remove_all",
    sub_cmd_description="Remove all culvert scores at a specific date.",
    options=[
        SlashCommandOption(
            name="target_date",
            description="Target date for removal. Format: YYYY-MM-DD.",
            required=True,
            type=OptionType.STRING
        ),
    ]
)
async def removeAll(ctx: SlashContext, target_date: str):
    def is_valid_date(date_str):
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
            return True
        except ValueError:
            return False
        
    if not is_valid_date(target_date):
        title_fail = 'Date is invalid.'
        description_fail = 'Enter the date in this format: YYYY-MM-DD.'
        color_fail = '#FF0000'
        thumbnail_fail = embed_thumbnails["sugar_fail"]
        embed_fail = create_embed(title_fail, description=description_fail, color=color_fail, thumbnail=thumbnail_fail)
        await ctx.send(embed=embed_fail)
        return -1
    
    title_inprogress = "Removing scores from the specified date!"
    description_inprogress = "This may take a few seconds."
    color_inprogress = "#FF9900"
    thumbnail_inprogress = embed_thumbnails["sugar_inprogress"]
    embed_inprogress = create_embed(title_inprogress, color=color_inprogress, description=description_inprogress, thumbnail=thumbnail_inprogress)
    embed_message = await ctx.send(embed=embed_inprogress)
    members = collection_scores.find({"date": target_date})
    if collection_scores.count_documents({"date": target_date}):
        for member in members:
            score_date_pairs = list(zip(member["score"], member["date"]))
            filtered_pairs = [pair for pair in score_date_pairs if pair[1] != target_date]
            if len(filtered_pairs) != len(score_date_pairs):
                new_scores, new_dates = zip(*filtered_pairs) if filtered_pairs else ([], [])
                collection_scores.update_one(
                    {'_id': member['_id']},
                    {'$set':
                        {
                            'score': new_scores,
                            'date': new_dates
                        }
                    }
                )
        title_success = 'Removed scores for all members at specified date.'
        color_success = '#2bff00'
        thumbnail_success = embed_thumbnails["sugar_done"]
        embed_success = create_embed(title_success, color=color_success, thumbnail=thumbnail_success)
        await embed_message.edit(embed=embed_success)
    else:
        title_fail = 'There are no members that contain that specified date.'
        description_error = f"The date, {target_date}, has not been logged for any member."
        color_fail = '#FF0000'
        thumbnail_fail = embed_thumbnails["sugar_fail"]
        embed_fail = create_embed(title_fail, color=color_fail, thumbnail=thumbnail_fail)
        await ctx.send(embed=embed_fail)
        return -1

@culvert_cmd.subcommand(
    sub_cmd_name="remove_one",
    sub_cmd_description="Remove a culvert score at a specific date for one member.",
    options=[
        SlashCommandOption(
            name="name",
            description="Guild member IGN.",
            required=True,
            type=OptionType.STRING
        ),
        SlashCommandOption(
            name="target_date",
            description="Target date for removal. Format: YYYY-MM-DD.",
            required=True,
            type=OptionType.STRING
        )
    ]
)
async def removeOne(ctx: SlashContext, name: str, target_date: str):
    def is_valid_date(date_str):
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
            return True
        except ValueError:
            return False
        # 28627 @ 2024-01-29
    if not is_valid_date(target_date):
        title_fail = 'Date is invalid.'
        description_fail = 'Enter the date in this format: YYYY-MM-DD.'
        color_fail = '#FF0000'
        thumbnail_fail = embed_thumbnails["sugar_fail"]
        embed_fail = create_embed(title_fail, description=description_fail, color=color_fail, thumbnail=thumbnail_fail)
        await ctx.send(embed=embed_fail)
        return -1
    
    member = collection_scores.find_one({"name": name.lower()})
    if member:
        if target_date in member["date"]:
            index = member["date"].index(target_date)
            new_scores = member["score"][:]
            new_dates = member["date"][:]
            new_scores.pop(index)
            new_dates.pop(index)
            
            collection_scores.update_one(
                {"name": name},
                {"$set":
                    {
                        "score": new_scores,
                        "date": new_dates
                    } 
                }
            )
            title_success = 'Removed score successfully!'
            color_success = '#2bff00'
            thumbnail_success = embed_thumbnails["sugar_done"]
            embed_success = create_embed(title_success, color=color_success, thumbnail=thumbnail_success)
            await ctx.send(embed=embed_success)
        else:
            title_fail = "Unable to find date!"
            description_fail = f"The date, {target_date}, has no log for {name}."
            color_fail = '#FF0000'
            thumbnail_fail = embed_thumbnails["sugar_fail"]
            embed_fail = create_embed(title_fail, color=color_fail, description=description_fail, thumbnail=thumbnail_fail)
            await ctx.send(embed=embed_fail)
            return -1
    else:
        title_fail = 'Member does not exist.'
        description_fail = f"{name} does not exist in the database."
        color_fail = '#FF0000'
        thumbnail_fail = embed_thumbnails["sugar_fail"]
        embed_fail = create_embed(title_fail, color=color_fail, description=description_fail, thumbnail=thumbnail_fail)
        await ctx.send(embed=embed_fail)
        return -1

@culvert_cmd.subcommand(
    sub_cmd_name="add_one",
    sub_cmd_description="Add a culvert score and date to a specific member.",
    options=[
        SlashCommandOption(
            name="name",
            description="Guild member IGN.",
            required=True,
            type=OptionType.STRING
        ),
        SlashCommandOption(
            name="date",
            description="Date of culvert score.",
            required=True,
            type=OptionType.STRING
        ),
        SlashCommandOption(
            name="score",
            description="Culvert score.",
            required=True,
            type=OptionType.INTEGER
        )
    ]
)
async def addOne(ctx: SlashContext, name: str, date: str, score: int):
    def is_valid_date(date_str):
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
            return True
        except ValueError:
            return False
        
    if not is_valid_date(date):
        title_fail = 'Date is invalid.'
        description_fail = 'Enter the date in this format: YYYY-MM-DD.'
        color_fail = '#FF0000'
        thumbnail_fail = embed_thumbnails["sugar_fail"]
        embed_fail = create_embed(title_fail, description=description_fail, color=color_fail, thumbnail=thumbnail_fail)
        await ctx.send(embed=embed_fail)
        return -1
    
    member = collection_scores.find_one({"name": name.lower()})
    if member:
        result = collection_scores.update_one(
            {"name": name},
            {"$push":
                {
                    "score": score,
                    "date": date
                }
            }
        )
        title_success = 'Score and date added!'
        color_success = '#2bff00'
        thumbnail_success = embed_thumbnails["sugar_done"]
        embed_success = create_embed(title_success, color=color_success, thumbnail=thumbnail_success)
        await ctx.send(embed=embed_success)
    else:
        title_fail = 'Member does not exist.'
        description_fail = f"{name} does not exist in the database."
        color_fail = '#FF0000'
        thumbnail_fail = embed_thumbnails["sugar_fail"]
        embed_fail = create_embed(title_fail, color=color_fail, description=description_fail, thumbnail=thumbnail_fail)
        await ctx.send(embed=embed_fail)
        return -1

@culvert_cmd.subcommand(sub_cmd_name="announce", sub_cmd_description="Announces the highlights of culvert this week.")
async def announce(ctx: SlashContext):
    player_scores_data = collection_scores.find({}, {"name": 1, "class": 1, "level": 1, "score": 1, "date": 1})
    player_scores_list = [{"name": doc["name"], "class": doc["class"], "level": doc["level"], "score": doc["score"], "date": doc["date"]} for doc in player_scores_data]
    scores_sorted_curweek = sorted(player_scores_list, key=lambda x: x["score"][-1], reverse=True)

    rank1_member = collection_names.find_one({"name_lower": scores_sorted_curweek[0]['name']})
    rank1_story = f"<@!{rank1_member['discord_id']}>" if rank1_member['discord_id'] is not None else rank1_member['name']
    rank1_story_value = scores_sorted_curweek[0]['score'][-1]
    rank2_member = collection_names.find_one({"name_lower": scores_sorted_curweek[1]['name']})
    rank2_story = f"<@!{rank2_member['discord_id']}>" if rank2_member['discord_id'] is not None else rank2_member['name']
    rank2_story_value = scores_sorted_curweek[1]['score'][-1]
    rank3_member = collection_names.find_one({"name_lower": scores_sorted_curweek[2]['name']})
    rank3_story = f"<@!{rank3_member['discord_id']}>" if rank3_member['discord_id'] is not None else rank3_member['name']
    rank3_story_value = scores_sorted_curweek[2]['score'][-1]

    scores_lastweek = []
    lowest_diff = None
    lowest_diff_indices = (None, None)
    biggest_improvement_member = None
    biggest_improvement = None
    for member in player_scores_list:
        if len(member['score']) >= 2:
            scores_lastweek.append(member)
            if member['score'][-1] == 0 or member['score'][-2] == 0:
                continue
            improvement = member['score'][-1] - member['score'][-2]
            if biggest_improvement is None or improvement > biggest_improvement:
                biggest_improvement_member = member
                biggest_improvement = improvement
    biggest_improvement_member_name = collection_names.find_one({"name_lower": biggest_improvement_member['name']})
    biggest_improvement_member_story = f"@<!{biggest_improvement_member_name['discord_id']}>" if biggest_improvement_member_name['discord_id'] is not None else biggest_improvement_member_name['name']

    scores_lastweek_sorted = sorted(scores_lastweek, key=lambda x: x["score"][-2], reverse=True)
    scores_differences_lastweek = []
    for i in range(1, len(scores_lastweek_sorted)):
        if scores_lastweek_sorted[i]['score'][-2] == 0 or scores_lastweek_sorted[i-1]['score'][-2] == 0:
            continue
        current_diff = scores_lastweek_sorted[i]['score'][-2] - scores_lastweek_sorted[i-1]['score'][-2]
        scores_differences_lastweek.append(current_diff)
        if lowest_diff is None or abs(current_diff) < abs(lowest_diff):
            lowest_diff = current_diff
            lowest_diff_indices = (i-1, i)
    lowest_diff_member0 = collection_names.find_one({"name_lower": scores_lastweek_sorted[lowest_diff_indices[0]]['name']})
    lowest_diff_member1 = collection_names.find_one({"name_lower": scores_lastweek_sorted[lowest_diff_indices[1]]['name']})
    lowest_diff_story0 = f"<@!{lowest_diff_member0['discord_id']}>" if lowest_diff_member0['discord_id'] is not None else lowest_diff_member0['name']
    lowest_diff_story1 = f"<@!{lowest_diff_member1['discord_id']}>" if lowest_diff_member1['discord_id'] is not None else lowest_diff_member1['name']
    
    lowest_diff_member0_score_currweek = collection_scores.find_one({"name":scores_lastweek_sorted[lowest_diff_indices[0]]['name']})['score'][-1]
    lowest_diff_member1_score_currweek = collection_scores.find_one({"name":scores_lastweek_sorted[lowest_diff_indices[1]]['name']})['score'][-1]
    title_waitGPT = "Generating the story!"
    description_waitGPT = "This could take up to 30 seconds."
    color_waitGPT = "#FF9900"
    thumbnail_waitGPT = embed_thumbnails["sugar_inprogress"]
    embed_waitGPT = create_embed(title_waitGPT, color=color_waitGPT, description=description_waitGPT, thumbnail=thumbnail_waitGPT)
    embed_waitGPT_message = await ctx.send(embed=embed_waitGPT)
    await ctx.send(f"{story_generator(rank1_story, rank1_story_value, rank2_story, rank2_story_value, rank3_story, rank3_story_value, biggest_improvement_member_story, biggest_improvement, lowest_diff_story0, lowest_diff_member0_score_currweek, lowest_diff_story1, lowest_diff_member1_score_currweek)}\n\n Good job this week everyone! Go Saga!")
    await embed_waitGPT_message.delete()

@culvert_cmd.subcommand(sub_cmd_name="changes")
async def changes(ctx: SlashContext):
    player_scores_data = collection_scores.find({}, {"name": 1, "class": 1, "level": 1, "score": 1, "date": 1})
    player_scores_list = [{"name": doc["name"], "class": doc["class"], "level": doc["level"], "score": doc["score"], "date": doc["date"]} for doc in player_scores_data]
    
    greatest_change = []
    for member in player_scores_list:
        if len(member['score']) > 1 and member['score'][-1] != 0:
            highest_score = max(member['score'][:-1])
            if highest_score == 0:
                continue
            change = member['score'][-1] - highest_score
            change_percent = change/highest_score*100
            discord_id = collection_names.find_one({'name_lower': member['name']})['discord_id']
            greatest_change.append({"name": member['name'], "change": change_percent, "discord_id": discord_id})
    greatest_change_sorted = sorted(greatest_change, key=lambda x: x['change'], reverse=True)
    for i in range(0, len(greatest_change_sorted)):
        print(f"{greatest_change_sorted[i]['name']} {round(greatest_change_sorted[i]['change'], 2)} {greatest_change_sorted[i]['discord_id']}")

@culvert_cmd.subcommand(sub_cmd_name="download", sub_cmd_description="Downloads the latest culvert scores read by the bot sorted in alphabetical order by member.")
async def download(ctx: SlashContext):
    latest_data = collection_scores.find({}, {'name': 1, 'score': 1})
    latest_scores = [{"name": doc["name"], "score": doc["score"][-1]} for doc in latest_data]
    latest_scores_sorted = sorted(latest_scores, key=lambda x: x["name"])
    df = pd.DataFrame(latest_scores_sorted)
    csv_file_path = 'latest_scores.csv'
    df.to_csv(csv_file_path, index=False)
    await ctx.send(file=File(csv_file_path))

@search_cmd.subcommand(
    sub_cmd_name="member", 
    sub_cmd_description="Display culvert scores based on the user provided.",
    options=[
        SlashCommandOption(
            name="name",
            description="Guild member's IGN.",
            required=True,
            type=OptionType.STRING
        )
    ]
)
async def search_by_member(ctx: SlashContext, name: str):
    member = collection_scores.find_one({"name": name.lower()})
    if member:
        player_scores_data = collection_scores.find({}, {"name": 1, "class": 1, "level": 1, "score": 1, "date": 1})
        player_scores_list = [{"name": doc["name"], "class": doc["class"], "level": doc["level"], "score": doc["score"], "date": doc["date"]} for doc in player_scores_data]
        players_to_compare = []
        for player in player_scores_list:
            for logged_date in player["date"]:
                if member["date"][-1] == logged_date:
                    players_to_compare.append(player)
                    continue
        players_to_compare_sorted = sorted(players_to_compare, key=lambda x: x["score"][x["date"].index(member["date"][-1])], reverse=True)
        member_rank = next(index for index, d in enumerate(players_to_compare_sorted) if d.get("name") == member["name"])
        member_page = math.ceil((member_rank+1)/17)
        member_page_digits = [int(char) for char in str(member_page)]
        member_class = member["class"]
        numbers_dict = {
            0: "0\uFE0F\u20E3",
            1: "1\uFE0F\u20E3",
            2: "2\uFE0F\u20E3",
            3: "3\uFE0F\u20E3",
            4: "4\uFE0F\u20E3",
            5: "5\uFE0F\u20E3",
            6: "6\uFE0F\u20E3",
            7: "7\uFE0F\u20E3",
            8: "8\uFE0F\u20E3",
            9: "9\uFE0F\u20E3"
        }
        emoji_string = ''.join(numbers_dict[digit] for digit in member_page_digits)
        member_case_correction = collection_names.find_one({"name_lower": name.lower()})
        embeds_pages = []
        title_shared = f'{member_case_correction["name"]}\'s Culvert Scores'
        description_graph = f'{member_case_correction["name"]} is a Level {member["level"]} {member["class"].title()}. \n\n Their most recently logged culvert score was {"{:,}".format(member["score"][-1])}, which ranks them at #{member_rank+1} out of all logged scores on that day. This makes them a {emoji_string}-pager.'
        color_shared = '#2bff00'
        thumbnail_shared = embed_thumbnails[member_class.lower()]
        footer_shared = f'Log date range: {datetime.strptime(member["date"][0], "%Y-%m-%d").strftime("%B %d, %Y")} to {datetime.strptime(member["date"][-1], "%Y-%m-%d").strftime("%B %d, %Y")}'
        embed_graph = create_embed(title_shared, description=description_graph, color=color_shared, thumbnail=thumbnail_shared, footer=footer_shared)
        embeds_pages.append(embed_graph)

        scores_reversed = list(reversed(member["score"]))
        dates_reversed = list(reversed(member["date"]))
        scores_field = ''
        dates_field = ''
        for index, scores in enumerate(scores_reversed):
            scores_field += f'{"{:,}".format(scores)}\n'
            dates_field += f'{dates_reversed[index]}\n'
            if (index+1) % 20 == 0:
                description_data = "All logged scores sorted from most recent to earliest."
                fields_data = [
                    {
                        "name": "Date",
                        "value": dates_field,
                        "inline": True
                    },
                    {
                        "name": "Scores",
                        "value": scores_field,
                        "inline": True
                    }
                ]
                embeds_pages.append(create_embed(title_shared, description=description_graph, color=color_shared, footer=footer_shared, thumbnail=thumbnail_shared, field=fields_data))
                scores_field = ''
                dates_field = ''
        if scores_field != '':
            description_data = "All logged scores sorted from most recent to earliest"
            fields_data = [
                {
                    "name": "Date",
                    "value": dates_field,
                    "inline": True
                },
                {
                    "name": "Scores",
                    "value": scores_field,
                    "inline": True
                }
            ]
            embeds_pages.append(create_embed(title_shared, description=description_data, color=color_shared, footer=footer_shared, thumbnail=thumbnail_shared, field=fields_data))
            scores_field = ''
            dates_field = ''

        paginator = Paginator.create_from_embeds(bot, *embeds_pages, timeout=120)
        await paginator.send(ctx)

        x = member["date"]
        y = member["score"]
        plot_image = bytesio_to_image(plot_to_image(x, y))

        image_bytes = io.BytesIO()
        plot_image.save(image_bytes, format="PNG")
        image_bytes.seek(0)
        plot_dfile = File(image_bytes, file_name='image.png')
        plot_dfile_to_ctx = await ctx.send(file=plot_dfile)
        plot_url = plot_dfile_to_ctx.attachments[0].url
        embed_graph.set_image(url=plot_url)
        await plot_dfile_to_ctx.delete()

        paginator.pages[0] = embed_graph
        await paginator.message.edit(embed=paginator.pages[0])
    else:
        title_error = "No match found."
        description_error = f"{name} does not exist in the database."
        color_error = "#FF0000"
        thumbnail_error = embed_thumbnails["sugar_fail"]
        embed_error = create_embed(title_error, color=color_error, description=description_error, thumbnail=thumbnail_error)
        await ctx.send(embed=embed_error)

@search_cmd.subcommand(
    sub_cmd_name="date",
    sub_cmd_description="Display culvert scores based on the date provided.",
    options=[
        SlashCommandOption(
            name="date",
            description="Format: YYYY-MM-DD",
            required=True,
            type=OptionType.STRING
        )
    ]
)
async def search_by_date(ctx: SlashContext, date: str):
    # title_fail = 'Well this is unfortunate.'
    # description_fail = f"Command disabled. Debugging this as we speak (no im not)."
    # color_fail = '#FF0000'
    # thumbnail_fail = embed_thumbnails["sugar_fail"]
    # embed_fail = create_embed(title_fail, color=color_fail, description=description_fail, thumbnail=thumbnail_fail)
    # await ctx.send(embed=embed_fail)
    await ctx.defer()
    def is_valid_date(date_str):
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
            return True
        except ValueError:
            return False
    
    if not is_valid_date(date):
        title_fail = 'Date is invalid.'
        description_fail = 'Enter the date in this format: YYYY-MM-DD.'
        color_fail = '#FF0000'
        thumbnail_fail = embed_thumbnails["sugar_fail"]
        embed_fail = create_embed(title_fail, description=description_fail, color=color_fail, thumbnail=thumbnail_fail)
        await ctx.send(embed=embed_fail)
        return -1
        
    player_scores_data = collection_scores.find({}, {"name": 1, "class": 1, "level": 1, "score": 1, "date": 1})
    player_scores_list = [{"name": doc["name"], "class": doc["class"], "level": doc["level"], "score": doc["score"], "date": doc["date"]} for doc in player_scores_data]
    players_to_display = []
    
    for member in player_scores_list:
        for logged_date in member["date"]:
            if date == logged_date:
                players_to_display.append(member)
                continue
    if len(players_to_display) > 0:
        players_to_display_sorted = sorted(players_to_display, key=lambda x: x["score"][x["date"].index(date)], reverse=True)
        names_field = ''
        class_field = ''
        scores_field = ''
        embeds_pages = []
        title_data = f'Top Culvert Scores on {datetime.strptime(date, "%Y-%m-%d").strftime("%B %d, %Y")}'
        description_data = "There are at most 17 entries per page."
        color_data = '#2bff00'
        thumbnail_data = embed_thumbnails["sugar_done"]
        for index, member in enumerate(players_to_display_sorted):
            member_case_correction = collection_names.find_one({"name_lower": member["name"].lower()})
            class_field += f'{member["class"].title()}\n'
            scores_field += f'{"{:,}".format(member["score"][member["date"].index(date)])}\n'
            if index == 0:
                names_field += f'{member_case_correction["name"]} \U0001F947\n'
            elif index == 1:
                names_field += f'{member_case_correction["name"]} \U0001F948\n'
            elif index == 2:
                names_field += f'{member_case_correction["name"]} \U0001F949\n'
            else:
                names_field += f'{member_case_correction["name"]}\n'

            if (index+1) % 17 == 0:
                fields_data = [
                    {
                        "name": "Name",
                        "value": names_field,
                        "inline": True
                    },
                    {
                        "name": "Class",
                        "value": class_field,
                        "inline": True
                    },
                    {
                        "name": "Score",
                        "value": scores_field,
                        "inline": True
                    }
                ]
                embeds_pages.append(create_embed(title_data, description=description_data, color=color_data, thumbnail=thumbnail_data, field=fields_data))
                names_field = ''
                class_field = ''
                scores_field = ''

        if names_field != '':
            fields_data = [
                {
                    "name": "Name",
                    "value": names_field,
                    "inline": True
                },
                {
                    "name": "Class",
                    "value": class_field,
                    "inline": True
                },
                {
                    "name": "Score",
                    "value": scores_field,
                    "inline": True
                }
            ]
            embeds_pages.append(create_embed(title_data, description=description_data, color=color_data, thumbnail=thumbnail_data, field=fields_data))

        if len(embeds_pages) > 1:
            paginator = Paginator.create_from_embeds(bot, *embeds_pages, timeout=180)
            await paginator.send(ctx)
        else:
            await ctx.send(embed=embeds_pages[0])
    else:
        title_fail = 'No culvert scores were logged on this date.'
        description_fail = f"The date, {date}, does not have any culvert scores connected to it."
        color_fail = '#FF0000'
        thumbnail_fail = embed_thumbnails["sugar_fail"]
        embed_fail = create_embed(title_fail, color=color_fail, thumbnail=thumbnail_fail)
        await ctx.send(embed=embed_fail)

@search_cmd.subcommand(
    sub_cmd_name="class", 
    sub_cmd_description="Search the most recently logged culvert scores based on the class provided.",
    options=[
        SlashCommandOption(
            name="class_name",
            description="Type exactly as displayed in the guild window, i.e., Arch Mage (F/P)",
            required=True,
            type=OptionType.STRING
        )
    ]
)
async def search_class(ctx: SlashContext, class_name: str):
    class_scores_data = collection_scores.find({"class": class_name.lower()}, {"name": 1, "class": 1, "level": 1, "score": 1, "date": 1})
    class_scores_list = [{"name": doc["name"], "class": doc["class"], "level": doc["level"], "score": doc["score"], "date": doc["date"]} for doc in class_scores_data]
    if class_scores_list:
        embeds_pages = []
        class_scores_list_sorted = sorted(class_scores_list, key=lambda x: x["score"][-1], reverse=True)
        names_field = ''
        levels_field = ''
        scores_field = ''
        title_class = f"Top Culvert Scores for all {class_name.title()}s in the Guild"
        description_class = f"These were scored on {datetime.strptime(class_scores_list[0]['date'][-1], '%Y-%m-%d').strftime('%B %d, %Y')}."
        color_class = "#2bff00"
        thumbnail_class = embed_thumbnails[class_name.lower()]
        for index, member in enumerate(class_scores_list_sorted):
            member_case_correction = collection_names.find_one({"name_lower": member["name"].lower()})
            levels_field += f'{member["level"]}\n'
            scores_field += f'{"{:,}".format(member["score"][-1])}\n'
            if index == 0:
                names_field += f'{member_case_correction["name"]} \U0001F947\n'
            elif index == 1:
                names_field += f'{member_case_correction["name"]} \U0001F948\n'
            elif index == 2:
                names_field += f'{member_case_correction["name"]} \U0001F949\n'
            else:
                names_field += f'{member_case_correction["name"]}\n'

            if (index+1) % 10 == 0:
                fields_class = [
                    {
                        "name": "Name",
                        "value": names_field,
                        "inline": True
                    },
                    {
                        "name": "Level",
                        "value": levels_field,
                        "inline": True
                    },
                    {
                        "name": "Score",
                        "value": scores_field,
                        "inline": True
                    }
                ]
                embeds_pages.append(create_embed(title_class, description=description_class, color=color_class, thumbnail=thumbnail_class, field=fields_class))
                names_field = ''
                levels_field = ''
                scores_field = ''
        if names_field != '':
            fields_class = [
                {
                    "name": "Name",
                    "value": names_field,
                    "inline": True
                },
                {
                    "name": "Level",
                    "value": levels_field,
                    "inline": True
                },
                {
                    "name": "Score",
                    "value": scores_field,
                    "inline": True
                }
            ]
            embeds_pages.append(create_embed(title_class, description=description_class, color=color_class, thumbnail=thumbnail_class, field=fields_class))
    
        if len(embeds_pages) > 1:
            paginator = Paginator.create_from_embeds(bot, *embeds_pages, timeout=180)
            await paginator.send(ctx)
        else:
            await ctx.send(embed=embeds_pages[0])
    else:
        title_fail = 'Class does not exist.'
        description_fail = f"The class, {class_name}, does not exist."
        color_fail = '#FF0000'
        thumbnail_fail = embed_thumbnails["sugar_fail"]
        embed_fail = create_embed(title_fail, color=color_fail, description=description_fail, thumbnail=thumbnail_fail)
        await ctx.send(embed=embed_fail)
        
bot.start(TOKEN)