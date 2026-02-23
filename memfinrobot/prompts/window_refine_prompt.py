''' window refine（中文）'''


REFINE_PROMPT = """
你是一个专业的对话内容分析助手。基于 <current_query>，结合 <selected_content>，生成若干条“假设性指令（instructions）”。

这里的“假设性指令”指：与 <current_query> 明确语义相关的自然问题、线索或解释。

## 输入格式

<selected_content>

Jon said: Yeah definitely! Wanna see my moves next Fri? Can't wait!
Gina said: Sounds great, Jon! Next Friday works. Let's boogie!
Jon said: Wow, I'm excited too! This is gonna be great!
Gina said: Wow! What did you get?
Jon said: Woah, that pic's from when my dance crew took home first in a local comp last year. It was amazing up on that stage! I'm super keen to spread that intensity with other peeps. Gina, you ever been in any dance comps or shows?

<current_query>

Gina said: I used to compete in a few dance competitions and shows - my fav memory was when my team won first place at a regionals at age fifteen. It was an awesome feeling of accomplishment!

<selected_content> 是已筛选出的历史上下文，<current_query> 是当前发言。

---

## 任务

请根据 <selected_content> 生成一个 instructions 列表，用来支持、解释或补充 <current_query> 的语义理解。

instructions 可以是问题、线索、解释性陈述等。

---

## 要求

1. 输出必须为列表格式： ["instruction1","instruction2",...]。如果无需生成，返回 []。
2. 每条 instruction 都必须“简短、与 <current_query> 显式相关、并利用 <selected_content> 的上下文”。
3. 最多生成 3 条 instruction。
4. 不要输出与当前查询无关的泛化内容。

---

## 示例

### 示例 1

<selected_content>：

Jon said: Yeah definitely! Wanna see my moves next Fri? Can't wait!
Gina said: Sounds great, Jon! Next Friday works. Let's boogie!
Jon said: Wow, I'm excited too! This is gonna be great!
Gina said: Wow! What did you get?
Jon said: Woah, that pic's from when my dance crew took home first in a local comp last year. It was amazing up on that stage! I'm super keen to spread that intensity with other peeps. Gina, you ever been in any dance comps or shows?

<current_query>：

Gina said: I used to compete in a few dance competitions and shows - my fav memory was when my team won first place at a regionals at age fifteen. It was an awesome feeling of accomplishment!

输出：

["How old was Gina when she won first place in dance competitions?","Gina felt awesome when she won dance comps","Jon asked if Gina ever competed in dance shows or competitions."]

### 示例 2

<selected_content>：

Nate said: Good to know! I'll be sure to give you a shout whenever I run out of things to watch!
Joanna said: Sounds great! Let me know what you think of it when you're done!
Nate said: You bet! You'll be the first to know.
Joanna said: Awesome! Enjoy yourself!
Nate said: You too, take care!

<current_query>：

Joanna said: Later, take care!

输出：

[]

### 示例 3

<selected_content>：

Audrey said: Sounds great! I'd love to have more, but four is enough for now. They keep me busy and I want to make sure I give each of them the attention they deserve - four dogs is already a lot! I took them all to the vet and got them checked up, it was such a havoc that next time I'll bring them one by one.
Andrew said: Oof, that vet trip must have been chaotic. Yeah I'm sure they keep you busy! That photo you shared was sweet - do they have a favorite spot to relax?
Audrey said: Yeah, for sure. They each have their favorite spot to chill. Pepper loves lounging on the couch, Pixie always curls up in her bed, Precious has her chair, and Panda loves to relax on his rug! They all have their own little cozy spots.
Andrew said: That sounds adorable! Pets always find their own little spots and it brings so much joy and comfort. Here's Toby at his favorite spot.
Audrey said: Yeah, they sure know how to get comfy! Here's a pic of them snuggling on my favorite blanket.

<current_query>：

Andrew said: Aww, they're so adorable! They look so cozy. Do they always sleep like that?

输出：

["How does Andrew think of Audrey's pets?","Andrew said Audrey's pets looks cozy in blanket"]

---

## 输出格式（必须严格遵守）

<selected_content>
{selected_content}

<current_query>
{current_query}

输出必须是列表 ["instruction1","instruction2",...]，或 []。
不要输出任何额外文本。
不要输出任何额外文本。
不要输出任何额外文本。

只输出列表本身，不要解释。
"""
