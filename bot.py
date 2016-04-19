import logging
from datetime import datetime
from random import randint
from uuid import uuid4

from telegram import InlineQueryResultArticle, ParseMode, Message, Chat, \
    Emoji, InputTextMessageContent, InlineQueryResultCachedSticker as Sticker
from telegram.ext import Updater, InlineQueryHandler, \
    ChosenInlineResultHandler, CommandHandler, MessageHandler, filters
from telegram.utils.botan import Botan

from game_manager import GameManager
import card as c
from credentials import TOKEN, BOTAN_TOKEN
from start_bot import start_bot

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG)
logger = logging.getLogger(__name__)

gm = GameManager()
u = Updater(TOKEN)
dp = u.dispatcher

botan = False
if BOTAN_TOKEN:
    botan = Botan(BOTAN_TOKEN)

help_text = "Follow these steps:\n\n" \
            "1. Add this bot to a group\n" \
            "2. In the group, start a new game with /new or join an already" \
            " running game with /join\n" \
            "3. After at least two players have joined, start the game with" \
            " /start\n" \
            "4. Type <code>@mau_mau_bot</code> into your chat box and hit " \
            "space, or click the <code>via @mau_mau_bot</code> text next to " \
            "messages. You will see your cards (some greyed out), any extra " \
            "options like drawing, and a <b>?</b> to see the current game " \
            "state. The greyed out cards are those you can not play at the " \
            "moment." \
            "Tap an option to execute the selected action. \n\n" \
            "Players can join the game at any time, though you currently " \
            "can not play more than one game at a time. To leave a game, " \
            "use /leave.\n" \
            "If you enjoy this bot, " \
            "<a href=\"https://telegram.me/storebot?start=mau_mau_bot\">" \
            "rate me</a>, join the " \
            "<a href=\"https://telegram.me/unobotupdates\">update channel</a>" \
            " and buy an UNO card game.\n"


def list_subtract(list1, list2):
    """ Helper function to subtract two lists and return the sorted result """
    list1 = list1.copy()

    for x in list2:
        list1.remove(x)

    return list(sorted(list1))


def display_name(user):
    """ Get the current players name including their username, if possible """
    user_name = user.first_name
    if user.username:
        user_name += ' (@' + user.username + ')'
    return user_name


def display_color(color):
    """ Convert a color code to actual color name """
    if color == "r":
        return Emoji.HEAVY_BLACK_HEART + " Red"
    if color == "b":
        return Emoji.BLUE_HEART + " Blue"
    if color == "g":
        return Emoji.GREEN_HEART + " Green"
    if color == "y":
        return Emoji.YELLOW_HEART + " Yellow"


def error(bot, update, error):
    """ Simple error handler """
    logger.exception(error)


def new_game(bot, update):
    """ Handler for the /new command """
    chat_id = update.message.chat_id
    if update.message.chat.type == 'private':
        help(bot, update)
    else:
        gm.new_game(chat_id)
        bot.sendMessage(chat_id,
                        text="Created a new game! Join the game with /join "
                             "and start the game with /start")
        if botan:
            botan.track(update.message, 'New games')


def join_game(bot, update):
    """ Handler for the /join command """
    chat_id = update.message.chat_id
    if update.message.chat.type == 'private':
        help(bot, update)
    else:
        joined = gm.join_game(chat_id, update.message.from_user)
        if joined:
            bot.sendMessage(chat_id,
                            text="Joined the game",
                            reply_to_message_id=update.message.message_id)
        elif joined is None:
            bot.sendMessage(chat_id,
                            text="No game is running at the moment. "
                                 "Create a new game with /new",
                            reply_to_message_id=update.message.message_id)
        else:
            bot.sendMessage(chat_id,
                            text="You already joined the game. Start the game "
                                 "with /start",
                            reply_to_message_id=update.message.message_id)


def leave_game(bot, update):
    """ Handler for the /leave command """
    chat_id = update.message.chat_id
    game = gm.chatid_game[chat_id]
    user = update.message.from_user

    if game.current_player.user.id == user.id:
        bot.sendMessage(chat_id,
                        text="You can't leave the game if it's your turn")
    else:
        gm.leave_game(user)
        bot.sendMessage(chat_id, text="Okay")


def status_update(bot, update):
    """ Remove player from game if user leaves the group """

    if update.message.left_chat_member:
        try:
            chat_id = update.message.chat_id
            game = gm.chatid_game[chat_id]
            user = update.message.left_chat_member
        except KeyError:
            return

        user_ids = list()
        current_player = game.current_player
        user_ids.append(current_player.user.id)

        itplayer = current_player.next

        while itplayer is not current_player:
            user_ids.append(itplayer.user.id)
            itplayer = itplayer.next

        if user.id in user_ids:
            gm.leave_game(user)
            bot.sendMessage(chat_id, text="Removing %s from the game"
                                          % display_name(user))


def start_game(bot, update):
    """ Handler for the /start command """

    if update.message.chat.type != 'private':
        # Show the first card
        chat_id = update.message.chat_id
        game = gm.chatid_game[chat_id]

        if game.current_player is None or \
                game.current_player is game.current_player.next:
            bot.sendMessage(chat_id, text="At least two players must /join "
                                          "the game before you can start it")
        elif game.started:
            bot.sendMessage(chat_id, text="The game has already started")
        else:
            game.play_card(game.last_card)
            game.started = True
            bot.sendSticker(chat_id,
                            sticker=c.STICKERS[str(game.last_card)])
            bot.sendMessage(chat_id,
                            text="First player: " +
                                 display_name(game.current_player.user))
    else:
        help(bot, update)


def help(bot, update):
    """ Handler for the /help command """
    bot.sendMessage(update.message.chat_id,
                    text=help_text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True)


def news(bot, update):
    """ Handler for the /news command """
    bot.sendMessage(update.message.chat_id,
                    text="All news here: https://telegram.me/unobotupdates",
                    disable_web_page_preview=True)


def reply_to_query(bot, update):
    """ Builds the result list for inline queries and answers to the client """
    results = list()
    playable = list()

    try:
        user_id = update.inline_query.from_user.id
        player = gm.userid_player[user_id]
        game = gm.userid_game[user_id]
    except KeyError:
        add_no_game(results)
    else:
        if not game.started:
            add_not_started(results)
        elif user_id == game.current_player.user.id:
            if game.choosing_color:
                add_choose_color(results)
            else:
                if not player.drew:
                    add_draw(player, results)

                else:
                    add_pass(results)

                if game.last_card.special == c.DRAW_FOUR and game.draw_counter:
                    add_call_bluff(results)

                playable = player.playable_cards()

                for card in sorted(player.cards):
                    add_play_card(game, card, results,
                                  can_play=(card in playable))

        if False or game.choosing_color:
            add_other_cards(playable, player, results, game)
        elif user_id != game.current_player.user.id or not game.started:
            for card in sorted(player.cards):
                add_play_card(game, card, results, can_play=False)
        else:
            add_gameinfo(game, results)

        for result in results:
            result.id += ':%d' % player.anti_cheat

    bot.answerInlineQuery(update.inline_query.id, results, cache_time=0)


def add_choose_color(results):
    for color in c.COLORS:
        results.append(
            InlineQueryResultArticle(
                id=color,
                title="Choose Color",
                description=display_color(color),
                input_message_content=
                InputTextMessageContent(display_color(color))
            )
        )


def add_other_cards(playable, player, results, game):
    if not playable:
        playable = list()

    players = player_list(game)

    results.append(
        InlineQueryResultArticle(
            "hand",
            title="Cards (tap for game state):",
            description=', '.join([repr(card) for card in
                                   list_subtract(player.cards, playable)]),
            input_message_content=InputTextMessageContent(
                "Current player: " + display_name(game.current_player.user) +
                "\n" +
                "Last card: " + repr(game.last_card) + "\n" +
                "Players: " + " -> ".join(players))
        )
    )


def player_list(game):
    players = list()
    current_player = game.current_player
    itplayer = current_player.next
    add_player(current_player, players)
    while itplayer is not current_player:
        add_player(itplayer, players)
        itplayer = itplayer.next
    return players


def add_no_game(results):
    results.append(
        InlineQueryResultArticle(
            "nogame",
            title="You are not playing",
            input_message_content=
            InputTextMessageContent('Not playing right now. Use /new to start '
                                    'a game or /join to join the current game '
                                    'in this group')
        )
    )


def add_not_started(results):
    results.append(
        InlineQueryResultArticle(
            "nogame",
            title="The game wasn't started yet",
            input_message_content=
            InputTextMessageContent('Start the game with /start')
        )
    )


def add_draw(player, results):
    results.append(
        Sticker(
            "draw", sticker_file_id=c.STICKERS['option_draw'],
            input_message_content=
            InputTextMessageContent('Drawing %d card(s)'
                                    % (player.game.draw_counter or 1))
        )
    )


def add_gameinfo(game, results):
    players = player_list(game)

    results.append(
        Sticker(
            "gameinfo",
            sticker_file_id=c.STICKERS['option_info'],
            input_message_content=InputTextMessageContent(
                "Current player: " + display_name(game.current_player.user) +
                "\n" +
                "Last card: " + repr(game.last_card) + "\n" +
                "Players: " + " -> ".join(players))
        )
    )


def add_pass(results):
    results.append(
        Sticker(
            "pass", sticker_file_id=c.STICKERS['option_pass'],
            input_message_content=InputTextMessageContent('Pass')
        )
    )


def add_call_bluff(results):
    results.append(
        Sticker(
            "call_bluff",
            sticker_file_id=c.STICKERS['option_bluff'],
            input_message_content=
            InputTextMessageContent("I'm calling your bluff!")
        )
    )


def add_play_card(game, card, results, can_play):
    players = player_list(game)

    if can_play:
        results.append(
            Sticker(str(card), sticker_file_id=c.STICKERS[str(card)])
        )
    else:
        results.append(
            Sticker(str(uuid4()), sticker_file_id=c.STICKERS_GREY[str(card)],
                    input_message_content=InputTextMessageContent(
                        "Current player: " + display_name(
                            game.current_player.user) +
                        "\n" +
                        "Last card: " + repr(game.last_card) + "\n" +
                        "Players: " + " -> ".join(players)))
        )


def add_player(itplayer, players):
    players.append(itplayer.user.first_name + " (%d cards)"
                   % len(itplayer.cards))


def process_result(bot, update):
    """ Check the players actions and act accordingly """
    try:
        user = update.chosen_inline_result.from_user
        game = gm.userid_game[user.id]
        player = gm.userid_player[user.id]
        result_id = update.chosen_inline_result.result_id
        chat_id = gm.chatid_game[game]
    except KeyError:
        return

    logger.debug("Selected result: " + result_id)

    result_id, anti_cheat = result_id.split(':')
    last_anti_cheat = player.anti_cheat
    player.anti_cheat += 1

    if result_id in ('hand', 'gameinfo', 'nogame'):
        return
    elif len(result_id) == 36:  # UUID result
        return
    elif int(anti_cheat) != last_anti_cheat:
        bot.sendMessage(chat_id,
                        text="Cheat attempt by %s" % display_name(player.user))
        return
    elif result_id == 'call_bluff':
        do_call_bluff(bot, chat_id, game, player)
    elif result_id == 'draw':
        do_draw(game, player)
    elif result_id == 'pass':
        game.turn()
    elif result_id in c.COLORS:
        game.choose_color(result_id)
    else:
        do_play_card(bot, chat_id, game, player, result_id, user)

    if game.current_player.next:
        bot.sendMessage(chat_id, text="Next player: " +
                                      display_name(game.current_player.user))


def do_play_card(bot, chat_id, game, player, result_id, user):
    card = c.from_str(result_id)
    game.play_card(card)
    player.cards.remove(card)
    if game.choosing_color:
        bot.sendMessage(chat_id, text="Please choose a color")
    if len(player.cards) == 1:
        bot.sendMessage(chat_id, text="Last Card!")
    if len(player.cards) == 0:
        gm.leave_game(user)
        bot.sendMessage(chat_id, text="Player won!")
        if game.current_player is game.current_player.next:
            bot.sendMessage(chat_id, text="Game ended!")
            gm.end_game(chat_id)

    if botan:
        botan.track(Message(randint(1, 1000000000), user, datetime.now(),
                            Chat(chat_id, 'group')),
                    'Played cards')


def do_draw(game, player):
    draw_counter_before = game.draw_counter
    for n in range(game.draw_counter or 1):
        player.cards.append(game.deck.draw())
    game.draw_counter = 0
    player.drew = True
    if (game.last_card.value == c.DRAW_TWO or
        game.last_card.special == c.DRAW_FOUR) and \
            draw_counter_before > 0:
        game.turn()


def do_call_bluff(bot, chat_id, game, player):
    if player.prev.bluffing:
        bot.sendMessage(chat_id, text="Bluff called! Giving %d cards to %s"
                                      % (game.draw_counter,
                                         player.prev.user.first_name))
        for i in range(game.draw_counter):
            player.prev.cards.append(game.deck.draw())
    else:
        bot.sendMessage(chat_id, text="%s didn't bluff! Giving %d cards to"
                                      " %s"
                                      % (player.prev.user.first_name,
                                         game.draw_counter + 2,
                                         player.user.first_name))
        for i in range(game.draw_counter + 2):
            player.cards.append(game.deck.draw())
    game.draw_counter = 0
    game.turn()


# Add all handlers to the dispatcher and run the bot
dp.addHandler(InlineQueryHandler(reply_to_query))
dp.addHandler(ChosenInlineResultHandler(process_result))
dp.addHandler(CommandHandler('start', start_game))
dp.addHandler(CommandHandler('new', new_game))
dp.addHandler(CommandHandler('join', join_game))
dp.addHandler(CommandHandler('leave', leave_game))
dp.addHandler(CommandHandler('help', help))
dp.addHandler(CommandHandler('news', news))
dp.addHandler(MessageHandler([filters.STATUS_UPDATE], status_update))
dp.addErrorHandler(error)

start_bot(u)
u.idle()
