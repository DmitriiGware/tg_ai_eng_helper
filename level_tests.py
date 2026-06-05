import random


LEVEL_TESTS = {
    "A1": [
        {"topic": "to be", "question": "You want to say that you are happy now. Which English sentence is correct?", "options": ["I am happy.", "I is happy.", "I be happy."], "answer": "I am happy."},
        {"topic": "articles", "question": "Complete the sentence: I have ___ apple.", "options": ["an", "a", "the"], "answer": "an"},
        {"topic": "plural nouns", "question": "You talk about more than one book. Which plural form is correct?", "options": ["books", "bookes", "bookies"], "answer": "books"},
        {"topic": "present simple", "question": "You want to say that she drinks tea regularly. Which sentence is correct?", "options": ["She likes tea.", "She like tea.", "She liking tea."], "answer": "She likes tea."},
        {"topic": "possessive adjectives", "question": "Complete the sentence: This is ___ bag.", "options": ["my", "me", "I"], "answer": "my"},
        {"topic": "there is", "question": "You see one cat in the room. Which sentence is correct?", "options": ["There is a cat.", "There are a cat.", "There be a cat."], "answer": "There is a cat."},
        {"topic": "can", "question": "You want to say that you have the ability to swim. Which sentence is correct?", "options": ["I can swim.", "I can to swim.", "I cans swim."], "answer": "I can swim."},
        {"topic": "questions with do", "question": "You ask another person about pizza. Which question is correct?", "options": ["Do you like pizza?", "You do like pizza?", "Does you like pizza?"], "answer": "Do you like pizza?"},
        {"topic": "negative present simple", "question": "You want to say that you do not know something. Which sentence is correct?", "options": ["I don't know.", "I not know.", "I doesn't know."], "answer": "I don't know."},
        {"topic": "prepositions of place", "question": "Complete the sentence: The book is ___ the table.", "options": ["on", "at", "to"], "answer": "on"},
        {"topic": "have got", "question": "You want to say that you have a pen. Which sentence is correct?", "options": ["I have got a pen.", "I has got a pen.", "I got have a pen."], "answer": "I have got a pen."},
        {"topic": "demonstratives", "question": "You point to one object near you. Which word should you use?", "options": ["this", "these", "those"], "answer": "this"},
        {"topic": "basic adjectives", "question": "You describe something that is not big. Which word is the opposite of 'big'?", "options": ["small", "old", "fast"], "answer": "small"},
        {"topic": "time", "question": "You want to say that something happens at 5:00. Which phrase is correct?", "options": ["at five o'clock", "in five o'clock", "on five o'clock"], "answer": "at five o'clock"},
        {"topic": "countable nouns", "question": "You see two chairs. Which sentence is correct?", "options": ["There are two chairs.", "There is two chairs.", "There are two chair."], "answer": "There are two chairs."},
        {"topic": "object pronouns", "question": "Complete the sentence: I see ___ every day.", "options": ["him", "he", "his"], "answer": "him"},
        {"topic": "imperatives", "question": "You tell someone what to do with the door. Which instruction is correct?", "options": ["Open the door.", "Opens the door.", "To open the door."], "answer": "Open the door."},
        {"topic": "like + noun", "question": "You want to say that you enjoy music. Which sentence is correct?", "options": ["I like music.", "I like to music.", "I liking music."], "answer": "I like music."},
        {"topic": "short answers", "question": "Answer: Are you ready?", "options": ["Yes, I am.", "Yes, I do.", "Yes, I ready."], "answer": "Yes, I am."},
        {"topic": "days", "question": "Complete the phrase for a day of the week: ___ Monday.", "options": ["on", "in", "at"], "answer": "on"},
    ],
    "A2": [
        {"topic": "past simple regular", "question": "Complete the past sentence: I ___ TV yesterday.", "options": ["watched", "watch", "watching"], "answer": "watched"},
        {"topic": "past simple irregular", "question": "You want to say that she went home in the past. Which sentence is correct?", "options": ["She went home.", "She goed home.", "She goes home yesterday."], "answer": "She went home."},
        {"topic": "comparatives", "question": "You compare two books by price. Which sentence is correct?", "options": ["This book is cheaper.", "This book is more cheap.", "This book cheaper."], "answer": "This book is cheaper."},
        {"topic": "superlatives", "question": "Complete the sentence: This is ___ film I have ever seen.", "options": ["the best", "the goodest", "the better"], "answer": "the best"},
        {"topic": "going to", "question": "You plan to study later. Which sentence is correct?", "options": ["I am going to study.", "I going to study.", "I am go to study."], "answer": "I am going to study."},
        {"topic": "present continuous", "question": "People are playing right now. Which sentence is correct?", "options": ["They are playing.", "They is playing.", "They play now."], "answer": "They are playing."},
        {"topic": "much/many", "question": "Complete the question: How ___ water do you need?", "options": ["much", "many", "a lot"], "answer": "much"},
        {"topic": "some/any", "question": "You ask about questions in a neutral question. Which sentence is correct?", "options": ["Do you have any questions?", "Do you have some questions?", "Do you have a questions?"], "answer": "Do you have any questions?"},
        {"topic": "must", "question": "You tell someone that a seatbelt is necessary. Which sentence is correct?", "options": ["You must wear a seatbelt.", "You must to wear a seatbelt.", "You must wearing a seatbelt."], "answer": "You must wear a seatbelt."},
        {"topic": "should", "question": "You advise someone to rest. Which sentence is correct?", "options": ["You should rest.", "You should to rest.", "You should resting."], "answer": "You should rest."},
        {"topic": "will", "question": "You promise to call someone in the future. Which sentence is correct?", "options": ["I will call you.", "I will to call you.", "I call will you."], "answer": "I will call you."},
        {"topic": "adverbs", "question": "You describe how he speaks. Which sentence is correct?", "options": ["He speaks slowly.", "He speaks slow.", "He slow speaks."], "answer": "He speaks slowly."},
        {"topic": "prepositions of movement", "question": "Complete the sentence: She walked ___ the room.", "options": ["into", "on", "at"], "answer": "into"},
        {"topic": "because", "question": "You explain why you stayed home. Which sentence is correct?", "options": ["I stayed home because I was tired.", "I stayed home because of I was tired.", "I stayed home so I tired."], "answer": "I stayed home because I was tired."},
        {"topic": "too/enough", "question": "You mean that the temperature is more cold than comfortable. Which sentence is correct?", "options": ["It is too cold.", "It is enough cold.", "It too is cold."], "answer": "It is too cold."},
        {"topic": "infinitive of purpose", "question": "You came here because you want to learn. Which sentence is correct?", "options": ["I came here to learn.", "I came here for learn.", "I came here learning."], "answer": "I came here to learn."},
        {"topic": "past negative", "question": "You want to say you did not see him. Which sentence is correct?", "options": ["I didn't see him.", "I didn't saw him.", "I not saw him."], "answer": "I didn't see him."},
        {"topic": "past questions", "question": "You ask if someone liked an event yesterday. Which question is correct?", "options": ["Did you enjoy it?", "Did you enjoyed it?", "Enjoyed you it?"], "answer": "Did you enjoy it?"},
        {"topic": "frequency adverbs", "question": "You talk about a regular habit with 'usually'. Which sentence is correct?", "options": ["I usually drink coffee.", "I drink usually coffee.", "Usually I drink coffee always."], "answer": "I usually drink coffee."},
        {"topic": "requests", "question": "You politely ask another person for help. Which phrase is correct?", "options": ["Could you help me?", "Do help me?", "Can to help me?"], "answer": "Could you help me?"},
    ],
    "B1": [
        {"topic": "present perfect", "question": "You talk about life experience, not a specific time. Which sentence is correct?", "options": ["I have seen this film.", "I saw this film already.", "I have saw this film."], "answer": "I have seen this film."},
        {"topic": "present perfect vs past simple", "question": "Complete the sentence about a finished past time: I ___ him yesterday.", "options": ["saw", "have seen", "seen"], "answer": "saw"},
        {"topic": "first conditional", "question": "You talk about a real possible future situation. Which sentence is correct?", "options": ["If it rains, I will stay home.", "If it will rain, I stay home.", "If it rains, I stay home yesterday."], "answer": "If it rains, I will stay home."},
        {"topic": "second conditional", "question": "You imagine an unreal situation: you do not have time now. Which sentence is correct?", "options": ["If I had time, I would travel.", "If I have time, I would travel.", "If I had time, I will travel."], "answer": "If I had time, I would travel."},
        {"topic": "passive voice", "question": "The action happened to the letter yesterday. Which passive sentence is correct?", "options": ["The letter was sent yesterday.", "The letter sent yesterday.", "The letter was send yesterday."], "answer": "The letter was sent yesterday."},
        {"topic": "reported speech", "question": "Yesterday he said: 'I am tired.' How do you report it correctly?", "options": ["He said he was tired.", "He said he is tired yesterday.", "He said he tired."], "answer": "He said he was tired."},
        {"topic": "gerund after enjoy", "question": "After 'enjoy', which sentence is correct?", "options": ["I enjoy reading.", "I enjoy to read.", "I enjoy read."], "answer": "I enjoy reading."},
        {"topic": "used to", "question": "You lived here in the past, but not now. Which sentence is correct?", "options": ["I used to live here.", "I use to lived here.", "I used live here."], "answer": "I used to live here."},
        {"topic": "relative clauses", "question": "You describe the man who called you. Which relative clause is correct?", "options": ["The man who called is my teacher.", "The man which called is my teacher.", "The man called who is my teacher."], "answer": "The man who called is my teacher."},
        {"topic": "modals of obligation", "question": "You need to finish this today. Which sentence is correct?", "options": ["I have to finish this today.", "I must to finish this today.", "I have finish this today."], "answer": "I have to finish this today."},
        {"topic": "present perfect continuous", "question": "You started waiting an hour ago and you are still waiting. Which sentence is correct?", "options": ["I have been waiting for an hour.", "I have waited since an hour.", "I am waiting since an hour."], "answer": "I have been waiting for an hour."},
        {"topic": "phrasal verbs", "question": "In the sentence 'Do not give up', what does 'give up' mean?", "options": ["stop trying", "start quickly", "return something"], "answer": "stop trying"},
        {"topic": "so/such", "question": "You want to emphasise that an idea was very good. Which sentence is correct?", "options": ["It was such a good idea.", "It was so good idea.", "It was such good idea."], "answer": "It was such a good idea."},
        {"topic": "articles", "question": "You talk about useful information. Which sentence is correct?", "options": ["The information was useful.", "An information was useful.", "Information were useful."], "answer": "The information was useful."},
        {"topic": "question tags", "question": "You expect the person is coming and want confirmation. Which tag question is correct?", "options": ["You are coming, aren't you?", "You are coming, don't you?", "You are coming, are you?"], "answer": "You are coming, aren't you?"},
        {"topic": "past continuous", "question": "One action was in progress when another action happened. Which sentence is correct?", "options": ["I was cooking when he called.", "I cooked when he was calling.", "I was cook when he called."], "answer": "I was cooking when he called."},
        {"topic": "although", "question": "You contrast 'it was late' with 'we continued'. Which sentence is correct?", "options": ["Although it was late, we continued.", "Although it was late, but we continued.", "Despite it was late, we continued."], "answer": "Although it was late, we continued."},
        {"topic": "make/do", "question": "Which phrase is the natural collocation with 'decision'?", "options": ["make a decision", "do a decision", "create a decision"], "answer": "make a decision"},
        {"topic": "wish", "question": "You do not know the answer, but you want to. Which sentence is correct?", "options": ["I wish I knew the answer.", "I wish I know the answer.", "I wish I would know the answer."], "answer": "I wish I knew the answer."},
        {"topic": "indirect questions", "question": "You ask politely about where she lives. Which indirect question is correct?", "options": ["Do you know where she lives?", "Do you know where does she live?", "Do you know where she live?"], "answer": "Do you know where she lives?"},
    ],
    "B2": [
        {"topic": "mixed conditionals", "question": "Past studying would change your confidence now. Which mixed conditional is correct?", "options": ["If I had studied, I would be confident now.", "If I studied, I would have been confident now.", "If I had studied, I will be confident now."], "answer": "If I had studied, I would be confident now."},
        {"topic": "third conditional", "question": "She left too late and missed the correct time. Which third conditional is correct?", "options": ["If she had left earlier, she would have arrived on time.", "If she left earlier, she would have arrived on time.", "If she had left earlier, she would arrive on time."], "answer": "If she had left earlier, she would have arrived on time."},
        {"topic": "advanced passive", "question": "People believe the project will be successful. Which passive reporting sentence is correct?", "options": ["The project is believed to be successful.", "The project believes to be successful.", "The project is believed being successful."], "answer": "The project is believed to be successful."},
        {"topic": "relative clauses", "question": "You add extra information about your brother, who lives abroad. Which sentence is correct?", "options": ["My brother, who lives abroad, is visiting us.", "My brother which lives abroad is visiting us.", "My brother, that lives abroad, is visiting us."], "answer": "My brother, who lives abroad, is visiting us."},
        {"topic": "inversion", "question": "You start with 'Rarely' for emphasis. Which word order is correct?", "options": ["Rarely have I seen such a view.", "Rarely I have seen such a view.", "Rarely have seen I such a view."], "answer": "Rarely have I seen such a view."},
        {"topic": "deduction", "question": "You are almost sure he forgot. Which sentence is correct?", "options": ["He must have forgotten.", "He must forgot.", "He must has forgotten."], "answer": "He must have forgotten."},
        {"topic": "future perfect", "question": "You expect the work to be completed before Friday. Which sentence is correct?", "options": ["By Friday, I will have finished it.", "By Friday, I will finish it already.", "By Friday, I will have finish it."], "answer": "By Friday, I will have finished it."},
        {"topic": "future continuous", "question": "You describe an action in progress at this time tomorrow. Which sentence is correct?", "options": ["This time tomorrow, I will be flying.", "This time tomorrow, I will flyed.", "This time tomorrow, I will flying."], "answer": "This time tomorrow, I will be flying."},
        {"topic": "verb patterns", "question": "You feel sorry about something you already told him. Which sentence is correct?", "options": ["I regret telling him.", "I regret to telling him.", "I regret tell him."], "answer": "I regret telling him."},
        {"topic": "participle clauses", "question": "She finished the work first, then left. Which participle clause is correct?", "options": ["Having finished the work, she left.", "Had finished the work, she left.", "Having finish the work, she left."], "answer": "Having finished the work, she left."},
        {"topic": "linking words", "question": "You want to contrast with the previous idea. Which connector fits best?", "options": ["Nevertheless", "Because of", "Despite of"], "answer": "Nevertheless"},
        {"topic": "collocations", "question": "Which phrase is the natural collocation with 'awareness'?", "options": ["raise awareness", "lift awareness", "grow awareness"], "answer": "raise awareness"},
        {"topic": "subjunctive", "question": "In a formal sentence after 'It is important that...', which form is correct?", "options": ["It is important that he be informed.", "It is important that he is informed.", "It is important that he will be informed."], "answer": "It is important that he be informed."},
        {"topic": "cleft sentences", "question": "You want to emphasise that you need more time. Which cleft sentence is correct?", "options": ["What I need is more time.", "That I need is more time.", "What I need it is more time."], "answer": "What I need is more time."},
        {"topic": "emphasis", "question": "You start with 'Not only' for emphasis. Which sentence is correct?", "options": ["Not only did she apologize, but she also helped.", "Not only she apologized, but she also helped.", "Not only did she apologized, but she also helped."], "answer": "Not only did she apologize, but she also helped."},
        {"topic": "articles with abstract nouns", "question": "You speak about education in general. Which sentence is correct?", "options": ["Education is important.", "The education is important in general.", "An education is important in general."], "answer": "Education is important."},
        {"topic": "formal vocabulary", "question": "In 'We need to postpone the meeting', what does 'postpone' mean?", "options": ["delay", "cancel", "repeat"], "answer": "delay"},
        {"topic": "modals in the past", "question": "You think someone made a mistake by not calling you. Which sentence is correct?", "options": ["You should have called me.", "You should called me.", "You should have call me."], "answer": "You should have called me."},
        {"topic": "reported questions", "question": "She asked: 'Where were you?' Which reported question is correct?", "options": ["She asked where I had been.", "She asked where had I been.", "She asked where I have been yesterday."], "answer": "She asked where I had been."},
        {"topic": "concession", "question": "He was tired, but he continued. Which sentence with 'despite' is correct?", "options": ["Despite being tired, he continued.", "Despite he was tired, he continued.", "Despite of being tired, he continued."], "answer": "Despite being tired, he continued."},
    ],
    "C1": [
        {"topic": "nuanced modals", "question": "You think it is quite possible that he is right. Which sentence sounds natural?", "options": ["He may well be right.", "He may good be right.", "He may be well right."], "answer": "He may well be right."},
        {"topic": "hedging", "question": "You want to write cautiously in an academic style. Which phrase is best?", "options": ["This appears to suggest a pattern.", "This proves always a pattern.", "This surely says a pattern."], "answer": "This appears to suggest a pattern."},
        {"topic": "advanced inversion", "question": "You start with 'Under no circumstances' for strong prohibition. Which word order is correct?", "options": ["Under no circumstances should you open it.", "Under no circumstances you should open it.", "Under no circumstances should open you it."], "answer": "Under no circumstances should you open it."},
        {"topic": "nominalisation", "question": "You need a formal sentence about a delayed plan. Which option is best?", "options": ["The implementation of the plan was delayed.", "They delayed to implement the plan.", "The plan was delayed to implement."], "answer": "The implementation of the plan was delayed."},
        {"topic": "ellipsis", "question": "Some people liked it and other people did not like it. Which shortened sentence is correct?", "options": ["Some liked it; others didn't.", "Some liked it; others didn't liked.", "Some liked it; others not."], "answer": "Some liked it; others didn't."},
        {"topic": "discourse markers", "question": "You introduce an opposite point in a formal text. Which marker fits best?", "options": ["Conversely", "Likewise", "Namely"], "answer": "Conversely"},
        {"topic": "advanced conditionals", "question": "Without your help, I would fail. Which formal conditional is correct?", "options": ["Were it not for your help, I would fail.", "Was it not for your help, I would fail.", "Were it not your help, I would fail."], "answer": "Were it not for your help, I would fail."},
        {"topic": "reduced clauses", "question": "The people were invited to the event and arrived early. Which reduced clause is correct?", "options": ["The people invited to the event arrived early.", "The people were invited to the event arrived early.", "The people inviting to the event arrived early."], "answer": "The people invited to the event arrived early."},
        {"topic": "subtle vocabulary", "question": "In 'mitigate the risk', what does 'mitigate' mean?", "options": ["reduce the effect of", "make completely worse", "ignore carefully"], "answer": "reduce the effect of"},
        {"topic": "formal register", "question": "In formal writing, which word can replace 'help'?", "options": ["assist", "make up", "sort out"], "answer": "assist"},
        {"topic": "preposition patterns", "question": "You say one idea matches another idea. Which phrase is correct?", "options": ["be consistent with", "be consistent to", "be consistent for"], "answer": "be consistent with"},
        {"topic": "emphatic structures", "question": "You want to emphasise that the timing caused the issue. Which sentence is correct?", "options": ["It was the timing that caused the issue.", "It was the timing what caused the issue.", "It was timing caused the issue."], "answer": "It was the timing that caused the issue."},
        {"topic": "advanced passive reporting", "question": "People think he left earlier. Which passive reporting sentence is correct?", "options": ["He is thought to have left.", "He is thought that left.", "He thought to have left."], "answer": "He is thought to have left."},
        {"topic": "concession clauses", "question": "You mostly agree, but you still see risks. Which sentence is correct?", "options": ["Much as I agree, there are risks.", "Much as I am agree, there are risks.", "As much I agree, there are risks."], "answer": "Much as I agree, there are risks."},
        {"topic": "adverb position", "question": "She arrived, and immediately after that it started raining. Which sentence is natural?", "options": ["She had barely arrived when it started raining.", "She barely had arrived when it started raining.", "Barely she had arrived when it started raining."], "answer": "She had barely arrived when it started raining."},
        {"topic": "collocation", "question": "Which phrase is the natural collocation with 'distinction'?", "options": ["draw a distinction", "paint a distinction", "make a distinguishing"], "answer": "draw a distinction"},
        {"topic": "register awareness", "question": "You need a neutral formal phrase before adding an observation. Which option fits?", "options": ["It is worth noting that...", "You gotta know that...", "It is super obvious that..."], "answer": "It is worth noting that..."},
        {"topic": "complex noun phrases", "question": "You describe demand for housing that is increasing quickly. Which phrase is correct?", "options": ["a rapidly growing demand for housing", "a demand rapidly growing for housing", "a rapid growing demand to housing"], "answer": "a rapidly growing demand for housing"},
        {"topic": "advanced linking", "question": "You want to add another supporting point. Which linking word fits best?", "options": ["Furthermore", "Although", "Unless"], "answer": "Furthermore"},
        {"topic": "stance", "question": "You want to make a careful claim about the data. Which statement is cautious?", "options": ["The data may indicate a shift.", "The data definitely solves everything.", "The data cannot never change."], "answer": "The data may indicate a shift."},
    ],
    "C2": [
        {"topic": "idiomatic precision", "question": "You want to say the proposal is not good enough. Which idiomatic sentence is correct?", "options": ["The proposal leaves much to be desired.", "The proposal leaves many to desire.", "The proposal leaves desired much."], "answer": "The proposal leaves much to be desired."},
        {"topic": "subtle emphasis", "question": "You want to say the delay makes the situation worse. Which sentence is correct?", "options": ["What makes matters worse is the delay.", "What makes worse matters is the delay.", "What matter worse is the delay."], "answer": "What makes matters worse is the delay."},
        {"topic": "advanced register", "question": "You write formally that the results do not give a clear answer. Which option is best?", "options": ["The findings are inconclusive.", "The findings are kind of unclear.", "The findings don't really say stuff."], "answer": "The findings are inconclusive."},
        {"topic": "rare inversion", "question": "You imagine a past situation: if I had known, I would have acted differently. Which inverted form is correct?", "options": ["Had I known, I would have acted differently.", "Had I knew, I would have acted differently.", "If had I known, I would have acted differently."], "answer": "Had I known, I would have acted differently."},
        {"topic": "nuanced vocabulary", "question": "In 'smartphones are ubiquitous', what does 'ubiquitous' mean?", "options": ["found everywhere", "very rare", "recently invented"], "answer": "found everywhere"},
        {"topic": "concision", "question": "You need a concise formal way to say the issue needs more study. Which sentence is best?", "options": ["The issue warrants further investigation.", "The issue is something that needs looking into more.", "The issue should maybe be checked more again."], "answer": "The issue warrants further investigation."},
        {"topic": "fixed expressions", "question": "Which fixed expression means 'in practical terms'?", "options": ["for all intents and purposes", "for all intensive purposes", "for every intent purposes"], "answer": "for all intents and purposes"},
        {"topic": "advanced concession", "question": "You accept the previous point but say you must continue. Which sentence is correct?", "options": ["Be that as it may, we must proceed.", "Be it as may that, we must proceed.", "As it may be that, we must proceed."], "answer": "Be that as it may, we must proceed."},
        {"topic": "semantic nuance", "question": "In 'She was reluctant to agree', what does 'reluctant' mean?", "options": ["unwilling", "careless", "delighted"], "answer": "unwilling"},
        {"topic": "formal cohesion", "question": "You acknowledge a limitation but continue the argument. Which formal connector fits?", "options": ["Notwithstanding this limitation", "Because this limitation of", "Anyway limitation"], "answer": "Notwithstanding this limitation"},
        {"topic": "complex passive", "question": "People expect the policy revision to be complete by June. Which sentence is correct?", "options": ["The policy is expected to have been revised by June.", "The policy expects to have revised by June.", "The policy is expected having revised by June."], "answer": "The policy is expected to have been revised by June."},
        {"topic": "nominal style", "question": "You need a formal phrase meaning 'conditions got worse later'. Which option fits?", "options": ["the subsequent deterioration of conditions", "conditions got worse after", "the later bad getting of conditions"], "answer": "the subsequent deterioration of conditions"},
        {"topic": "advanced collocation", "question": "Which phrase is the natural collocation with 'challenge'?", "options": ["pose a challenge", "put a challenge", "make a challenge to exist"], "answer": "pose a challenge"},
        {"topic": "pragmatics", "question": "You want to criticise politely in a professional setting. Which sentence is most diplomatic?", "options": ["That may need further refinement.", "That is completely wrong.", "You failed to do that."], "answer": "That may need further refinement."},
        {"topic": "cleft nuance", "question": "You are concerned about the timing, not the cost. Which sentence is correct?", "options": ["What concerns me is not the cost but the timing.", "What concerns me it is not the cost but the timing.", "What me concerns is not cost but timing."], "answer": "What concerns me is not the cost but the timing."},
        {"topic": "advanced prepositions", "question": "You say something follows a tradition. Which phrase is correct?", "options": ["in keeping with tradition", "on keeping with tradition", "at keeping with tradition"], "answer": "in keeping with tradition"},
        {"topic": "legal/formal tone", "question": "In a formal text, which phrase can replace 'before'?", "options": ["prior to", "ahead on", "previous than"], "answer": "prior to"},
        {"topic": "subtle modal meaning", "question": "You criticise someone because they did not tell you earlier. Which sentence expresses that?", "options": ["You might have told me earlier.", "You might tell me earlier.", "You might have been tell me earlier."], "answer": "You might have told me earlier."},
        {"topic": "advanced discourse", "question": "You summarise several points and say they suggest caution. Which phrase is correct?", "options": ["Taken together, these points suggest caution.", "Taking together, these points suggest caution.", "Together taken, these points suggest caution."], "answer": "Taken together, these points suggest caution."},
        {"topic": "idiom", "question": "If something is 'a double-edged sword', what does it mean?", "options": ["something with both benefits and risks", "a perfect solution", "a useless tool"], "answer": "something with both benefits and risks"},
    ],
}


UNCLEAR_QUESTION_TEXTS = {
    "choose the correct sentence.",
    "choose the correct form.",
    "choose the best option.",
    "choose the correct phrase.",
    "choose the best connector.",
    "choose the correct question.",
    "choose the correct instruction.",
    "choose the polite request.",
    "choose the correct passive sentence.",
    "choose the correct reported speech.",
}


def is_clear_level_question(question: dict) -> bool:
    text = (question.get("question") or "").strip().lower()
    return bool(text) and text not in UNCLEAR_QUESTION_TEXTS


def get_level_test(level: str, count: int = 5) -> list[dict]:
    pool = [question for question in LEVEL_TESTS[level] if is_clear_level_question(question)]
    if len(pool) < count:
        pool = LEVEL_TESTS[level]
    questions = random.sample(pool, count)
    result = []

    for question in questions:
        options = question["options"].copy()
        random.shuffle(options)
        result.append({
            "topic": question["topic"],
            "question": question["question"],
            "options": options,
            "correct_index": options.index(question["answer"]),
            "answer": question["answer"],
        })

    return result
