import os
import tempfile
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
from openai import OpenAI

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError("❌ Не заданы TELEGRAM_TOKEN или OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

# память пользователей
users = {}

ROLES = {
    "general": "Ты универсальный полезный помощник, отвечаешь понятно и по делу.",
    "tutor": "Ты терпеливый репетитор, объясняешь просто и пошагово.",
    "programmer": "Ты опытный программист, отвечаешь чётко и по делу.",
    "psychologist": "Ты поддерживающий психолог, отвечаешь мягко и бережно."
}

def get_user(user_id):
    if user_id not in users:
        users[user_id] = {
            "role": "general",
            "history": []
        }
    return users[user_id]

def main_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💬 Общие", callback_data="role_general"),
            InlineKeyboardButton("🎓 Репетитор", callback_data="role_tutor")
        ],
        [
            InlineKeyboardButton("💻 Код", callback_data="role_programmer"),
            InlineKeyboardButton("🧠 Психолог", callback_data="role_psychologist")
        ],
        [
            InlineKeyboardButton("🧹 Очистить", callback_data="clear")
        ]
    ])

async def voice_to_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.message.from_user.id)

    voice = update.message.voice
    file = await context.bot.get_file(voice.file_id)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as f:
        ogg_path = f.name
        await file.download_to_drive(ogg_path)

    wav_path = ogg_path.replace(".ogg", ".wav")
    os.system(f"ffmpeg -y -i {ogg_path} {wav_path}")

    with open(wav_path, "rb") as audio:
        transcript = client.audio.transcriptions.create(
            file=audio,
            model="gpt-4o-transcribe"
        )

    text = transcript.text

    os.remove(ogg_path)
    os.remove(wav_path)

    # дальше используем тот же чат-код
    user["history"].append({"role": "user", "content": text})

    messages = [
        {"role": "system", "content": ROLES[user["role"]]}
    ] + user["history"][-10:]

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages
    )

    answer = response.choices[0].message.content
    user["history"].append({"role": "assistant", "content": answer})

    await update.message.reply_text(
        f"🎤 Ты сказал:\n{text}\n\n🤖 Ответ:\n{answer}",
        reply_markup=main_keyboard()
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
    "🤖 *Режимы работы бота*\n\n"
    "💬 *Общие* — универсальные вопросы и разговор\n"
    "🎓 *Репетитор* — обучение, объяснения, примеры\n"
    "💻 *Код* — программирование и технические задачи\n"
    "🧠 *Психолог* — поддержка и бережный диалог\n\n"
    "⬇️ Выбери режим кнопками ниже:",
    reply_markup=main_keyboard(),
    parse_mode="Markdown"
)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = get_user(query.from_user.id)

    if query.data.startswith("role_"):
        role = query.data.replace("role_", "")
        user["role"] = role
        user["history"].clear()

        await query.message.reply_text(
    f"✅ Режим переключён\n"
    f"🧠 *Текущий режим:* `{role}`\n"
    f"🗑 Контекст очищен.",
    reply_markup=main_keyboard(),
    parse_mode="Markdown"
)

    elif query.data == "clear":
        user["history"].clear()
        await query.message.reply_text("🧹 Диалог очищен.")

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.message.from_user.id)
    text = update.message.text

    user["history"].append({"role": "user", "content": text})

    messages = [
        {"role": "system", "content": ROLES[user["role"]]}
    ] + user["history"][-10:]  # ограничиваем контекст

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages
    )

    answer = response.choices[0].message.content

    user["history"].append({"role": "assistant", "content": answer})
    await update.message.reply_text(answer, reply_markup=main_keyboard())

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(MessageHandler(filters.VOICE, voice_to_text))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

print("ИИ-бот с памятью запущен...")
app.run_polling()
