from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI()

def story_generator(rank1, rank1_score, rank2, rank2_score, rank3, rank3_score,
                    biggest_improvement, biggest_improvement_value,
                    diff1, diff1_score, diff2, diff2_score):
  style = client.chat.completions.create(
    model="gpt-4",
    messages=[
      {"role": "user", "content": "Generate a random writing style."}
    ],
    temperature=1.5,
    max_tokens=100,
    top_p=1,
    frequency_penalty=0,
    presence_penalty=0
  )

  setting = client.chat.completions.create(
    model="gpt-4",
    messages=[
      {"role": "user", "content": "Generate a random setting in words."}
    ],
    temperature=0.8,
    max_tokens=1000,
    top_p=1,
    frequency_penalty=0,
    presence_penalty=0
  )

  time = client.chat.completions.create(
    model="gpt-4",
    messages=[
      {"role": "user", "content": "Generate a random time period."}
    ],
    temperature=0.8,
    max_tokens=1000,
    top_p=1,
    frequency_penalty=0,
    presence_penalty=0
  )

  story = client.chat.completions.create(
    model="gpt-4",
    messages=[
      {"role": "user", "content": f"The setting is \"{setting}\" in the \"{time}\" time period. Write in the style of a \"{style}\". Here are the details to develop the story around. There was a competition this week. {rank1}, {rank2}, {rank3} score top 3 with a score of {rank1_score}, {rank2_score}, {rank3_score}, respectively. Then, write about how {diff1} and {diff2} were close in score last week but the situation changed this week when {diff1} scored {diff1_score} and {diff2} scored {diff2_score}. Describe how one person is ahead of the other. Lastly, write about how {biggest_improvement} made the biggest improvement in their score, increasing by {biggest_improvement_value}. Only use approximately 200 words."}
    ],
    temperature=0.8,
    max_tokens=1000,
    top_p=1,
    frequency_penalty=0,
    presence_penalty=0
  )

  return story.choices[0].message.content