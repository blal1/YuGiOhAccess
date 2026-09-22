import logging
import wx
from ui.base_ui import VerticalMenu, InputUI, StatusMessage
from core import variables
from core import utils
from core.i18n import _

from ui import server_ui
from ui import deck_editor_ui
from ui import card_search_ui
from ui import replay_ui

logger = logging.getLogger(__name__)

@utils.ui_function
def first_ui_help_info(return_ui=None):
    if not return_ui:
        return_ui = first_ui
    menu = VerticalMenu(_("Welcome to YuGiOhAccess"), False)
    menu.append_item(_("Welcome to YuGiOhAccess. This menu will contain quick information about the keys needed to move around. Use the up and down arrow keys to navigate the menu."))
    menu.append_item(_("In most screens, you can press F1 to get help information. This will give you information about the keys needed to move around in that specific screen."))
    menu.append_item(_("When encountering a text field, you can just start typing to enter text into that field. An example is provided below."))
    menu.append_item(wx.TextCtrl, label=_("Type something here"))
    menu.append_item(_("When encountering a slider, use the left and right arrow keys to adjust the value of the slider. An example is provided below."))
    slider = menu.append_item(wx.Slider, label=_("This is a slider"))
    slider.SetRange(0, 100)
    slider.SetValue(50)
    menu.append_item(_("The same goes for combo boxes. Use the left and right arrow keys to navigate the options. The  option will automatically be selected when you press enter. An example is provided below."))
    choice = menu.append_item(wx.Choice, label=_("This is a combo box"), choices=[_("Option 1"), _("Option 2"), _("Option 3")])
    choice.SetSelection(1)
    menu.append_item(_("When encountering a checkbox, use the space bar to toggle the checkbox. An example is provided below."))
    menu.append_item(wx.CheckBox, label=_("This is a checkbox"))
    menu.append_item(_("Lastly a little about the duel field"))
    menu.append_item(_("When you are in a duel, the field is layed out in a grid, with your field being in the bottom half, and the opponent's field being in the top half. Use the arrow keys to navigate the field."))
    menu.append_item(_("Use space to read a card, and enter to open up the actions for that card."))
    menu.append_item(_("Use backspace to open tue duel menu, where you can perform actions like attacking, ending your turn, and more."))
    menu.append_item(_("Use escape to go back to the duel field from the action or duel menu."))
    menu.append_item(_("That's all for now. If you want to see this information again, you can find it in the help section of the main menu."), return_ui)
    menu.append_item(_("Press enter to continue"), return_ui)
    menu.set_help_text(_("Hey it's jessica, the developer of the YuGiOhAccess client, you found this little message, or maybe you were told it was here. Anyway. Welcome to YuGiOhAccess. This menu will contain quick information about the keys needed to move around. Use the up and down arrow keys to navigate the menu."))
    return menu

@utils.ui_function
def first_ui():
    if variables.config.get("first_time_run"):
        variables.config.set("first_time_run", False)
        # since it's the players, first time, we will do like any other game, and take them to the settings menu
        first_ui_help_info()
        return
    main_menu_view()
    return

def _open_deck_editor():
    deck_editor_ui.deck_editor_main_menu(main_menu_view)


def _open_card_search():
    card_search_ui.card_search_menu(main_menu_view)


def _open_replay_viewer():
    replay_ui.replay_viewer_menu(main_menu_view)


@utils.ui_function
def main_menu_view():
    _apply_pending_catalog_refresh()
    if isinstance(variables.DEV_OPTIONS.server, int):
        server_ui.server_selection_menu()
        return
    current_nickname = variables.config.get("nickname")
    main_menu = VerticalMenu(_("Main Menu"))
    main_menu.set_help_text(_("Main menu. Use the up and down arrow keys to navigate the menu, and press enter to select an option"))
    main_menu.append_item(_("YuGiOh Access, {version}").format(version=utils.version_string_to_pretty(variables.APP_VERSION)), None)
    main_menu.append_item(_("Play ({nickname})").format(nickname=current_nickname), server_ui.server_selection_menu)
    main_menu.append_item(
        _("Change nickname (currently {nickname})").format(nickname=current_nickname),
        lambda: change_nickname(current_nickname),
    )
    main_menu.append_item(_("Deck Editor"), _open_deck_editor)
    main_menu.append_item(_("Card Search"), _open_card_search)
    main_menu.append_item(_("Replay Viewer"), _open_replay_viewer)
    main_menu.append_item(_("Settings"), settings_menu)
    main_menu.append_item(_("Help"), help_menu_view)
    if not variables.IS_FROZEN:
        main_menu.append_item(_("Make Windbot deck"), make_windbot_deck)
        main_menu.append_item(_("Make deck string from Windbot deck"), make_deck_string_from_windbot_deck)
    main_menu.append_item(_("Exit"), wx.GetTopLevelWindows()[0].Close)
    utils.get_discord_presence_manager().update_presence(
        state=_("In the main menu"),
        details=_("Getting ready to duel"),
    )
    return main_menu


def _apply_pending_catalog_refresh():
    try:
        from ui import data_updater_ui
        data_updater_ui.apply_pending_background_catalog_refresh()
    except Exception:
        logger.exception("Failed to apply pending card catalog update")

@utils.ui_function
def change_nickname(current_nickname):
    nickname_input = InputUI(_("Change nickname"), default_value=current_nickname)
    new_nickname = nickname_input.show()
    if not new_nickname or new_nickname == current_nickname:
        utils.output(_("Nickname unchanged"))
        return main_menu_view()
    variables.config.set("nickname", new_nickname)
    utils.output(_("Changed nickname to {name}").format(name=new_nickname))
    return main_menu_view()
@utils.ui_function
def settings_menu(return_to=None):
    if not return_to:
        return_to = main_menu_view
    settings_menu = VerticalMenu(_("Settings"), False)
    music_volume_slider = settings_menu.append_item(wx.Slider, label=_("Music volume"))
    music_volume_slider.SetRange(0, 20)
    current_music_volume = utils.get_ui_stack().music_audio_manager.get_volume() * 20
    current_music_volume = int(current_music_volume)
    music_volume_slider.SetValue(current_music_volume)
    music_volume_slider.Bind(wx.EVT_SLIDER, on_music_volume_change)
    music_volume_slider.Bind(wx.EVT_SET_FOCUS, lambda event: utils.provide_tooltip(_("Use the left and right arrow keys to adjust the music volume")))
    sound_effects_volume_slider = settings_menu.append_item(wx.Slider, label=_("Sound effects volume"))
    sound_effects_volume_slider.SetRange(0, 20)
    current_sound_effects_volume = utils.get_ui_stack().sound_effects_audio_manager.get_volume() * 20
    current_sound_effects_volume = int(current_sound_effects_volume)
    sound_effects_volume_slider.SetValue(current_sound_effects_volume)
    sound_effects_volume_slider.Bind(wx.EVT_SLIDER, on_sound_effects_volume_change)
    sound_effects_volume_slider.Bind(wx.EVT_SET_FOCUS, lambda event: utils.provide_tooltip(_("Use the left and right arrow keys to adjust the sound effects volume")))
    hints_checkbox = settings_menu.append_item(wx.CheckBox, label=_("Enable hints"))
    hints_checkbox.SetValue(variables.config.get("enable_hints"))
    hints_checkbox.Bind(wx.EVT_CHECKBOX, lambda event: variables.config.set("enable_hints", event.IsChecked()))
    hints_checkbox.Bind(wx.EVT_SET_FOCUS, lambda event: utils.provide_tooltip(_("When checked, hints like this will be spoken after a short delay. When unchecked, hints will not be spoken")))
    screenreader_output_checkbox = settings_menu.append_item(wx.CheckBox, label=_("Only output to screenreader when game window is focused"))
    screenreader_output_checkbox.SetValue(variables.config.get("screenreader_output_only_on_application_focus"))
    screenreader_output_checkbox.Bind(wx.EVT_CHECKBOX, lambda event: variables.config.set("screenreader_output_only_on_application_focus", event.IsChecked()))
    screenreader_output_checkbox.Bind(wx.EVT_SET_FOCUS, lambda event: utils.provide_tooltip(_("When checked, the screenreader will only output text when the game window is focused. When unchecked, the screenreader will output text even if the window is in the background")))
    helper_zones_checkbox = settings_menu.append_item(wx.CheckBox, label=_("Enable helper zones"))
    helper_zones_checkbox.SetValue(variables.config.get("helper_zones"))
    helper_zones_checkbox.Bind(wx.EVT_CHECKBOX, lambda event: variables.config.set("helper_zones", event.IsChecked()))
    helper_zones_checkbox.Bind(wx.EVT_SET_FOCUS, lambda event: utils.provide_tooltip(_("When checked, empty zones between and to the left and right of the extra monster zones will be shown. When unchecked, these zones will not be shown. Enabling this, might help in navigate the duel field better for newer players")))
    rock_paper_scissors_behavior = settings_menu.append_item(wx.Choice, label=_("Rock paper scissors behavior for the bot"), choices=[_("Random"), _("Always show rock"), _("Always show paper"), _("Always show scissors")])
    existing_rock_paper_scissors_bot_behavior = variables.config.get("rock_paper_scissors_bot_behavior")
    if existing_rock_paper_scissors_bot_behavior == "random":
        rock_paper_scissors_behavior.SetSelection(0)
    elif existing_rock_paper_scissors_bot_behavior == "rock":
        rock_paper_scissors_behavior.SetSelection(1)
    elif existing_rock_paper_scissors_bot_behavior == "paper":
        rock_paper_scissors_behavior.SetSelection(2)
    elif existing_rock_paper_scissors_bot_behavior == "scissors":
        rock_paper_scissors_behavior.SetSelection(3)
    rock_paper_scissors_behavior.Bind(wx.EVT_CHOICE, on_rock_paper_scissors_bot_behavior_change)
    rock_paper_scissors_behavior.Bind(wx.EVT_SET_FOCUS, lambda event: utils.provide_tooltip(_("Select the behavior of the bot in rock paper scissors. Random is the default, the bot will randomly pick rock, paper or scissors. Always show rock, paper or scissors will make the bot always pick that option")))
    bot_chatter_checkbox = settings_menu.append_item(wx.CheckBox, label=_("Enable bot chatter during duels"))
    bot_chatter_checkbox.SetValue(variables.config.get("enable_bot_chat"))
    bot_chatter_checkbox.Bind(wx.EVT_CHECKBOX, lambda event: variables.config.set("enable_bot_chat", event.IsChecked()))
    bot_chatter_checkbox.Bind(wx.EVT_SET_FOCUS, lambda event: utils.provide_tooltip(_("When checked, the bot will say things during duels. When unchecked, the bot will not say anything")))
    from core.i18n import get_available_languages, setup as i18n_setup
    available_langs = get_available_languages()
    lang_codes = list(available_langs.keys())
    lang_names = list(available_langs.values())
    ui_language_choice = settings_menu.append_item(wx.Choice, label=_("UI Language"), choices=lang_names)
    current_ui_lang = variables.config.get("ui_language", "en")
    if current_ui_lang in lang_codes:
        ui_language_choice.SetSelection(lang_codes.index(current_ui_lang))
    else:
        ui_language_choice.SetSelection(0)
    def on_ui_language_change(event):
        idx = event.GetEventObject().GetSelection()
        selected_code = lang_codes[idx]
        variables.config.set("ui_language", selected_code)
        i18n_setup(selected_code)
        utils.output(_("UI language changed to {language}. Restart for full effect.").format(language=lang_names[idx]))
    ui_language_choice.Bind(wx.EVT_CHOICE, on_ui_language_change)
    ui_language_choice.Bind(wx.EVT_SET_FOCUS, lambda event: utils.provide_tooltip(_("Select the language for the user interface. Card names use a separate setting.")))

    card_language_choices = get_card_catalog_language_choices()
    card_language_names = [language for language, _label in card_language_choices]
    card_language_labels = [label for _language, label in card_language_choices]
    card_language_choice = settings_menu.append_item(wx.Choice, label=_("Card catalog language"), choices=card_language_labels)
    current_card_language = variables.config.get("language", "english")
    if current_card_language in card_language_names:
        card_language_choice.SetSelection(card_language_names.index(current_card_language))
    else:
        card_language_choice.SetSelection(0)
    card_language_choice.Bind(wx.EVT_CHOICE, lambda event: on_card_language_change(event, card_language_names))
    card_language_choice.Bind(wx.EVT_SET_FOCUS, lambda event: utils.provide_tooltip(_("Select the language used for card names, card descriptions, and duel card strings.")))

    settings_menu.append_item(_("Done"), return_to)
    return settings_menu


def get_card_catalog_language_names():
    handler = variables.LANGUAGE_HANDLER
    if not handler:
        return ["english"]
    languages = sorted(handler.languages.keys())
    if "english" in languages:
        languages.remove("english")
        languages.insert(0, "english")
    return languages or ["english"]


def get_card_catalog_language_display_name(language):
    names = {
        "english": _("English"),
        "german": _("German"),
        "japanese": _("Japanese"),
        "spanish": _("Spanish"),
        "portuguese": _("Portuguese"),
        "italian": _("Italian"),
        "french": _("French"),
        "thai": _("Thai"),
        "chinese": _("Chinese"),
        "korean": _("Korean"),
    }
    return names.get(language, language.replace("_", " ").title())


def get_card_catalog_language_choices():
    return [
        (language, get_card_catalog_language_display_name(language))
        for language in get_card_catalog_language_names()
    ]


def set_card_catalog_language(language):
    handler = variables.LANGUAGE_HANDLER
    if not handler or not handler.is_loaded(language):
        utils.output(_("Card catalog language {language} is not available.").format(
            language=get_card_catalog_language_display_name(language),
        ))
        return
    variables.config.set("language", language)
    handler.set_primary_language(language)
    utils.output(_("Card catalog language changed to {language}.").format(
        language=get_card_catalog_language_display_name(language),
    ))


def on_card_language_change(event, languages=None):
    choice = event.GetEventObject()
    selection = choice.GetSelection()
    if languages is None:
        languages = get_card_catalog_language_names()
    if selection < 0 or selection >= len(languages):
        return
    set_card_catalog_language(languages[selection])


def on_music_volume_change(event):
    volume = event.GetEventObject().GetValue()
    adjusted_volume = volume * 5
    float_volume = adjusted_volume / 100
    utils.get_ui_stack().music_audio_manager.set_volume(float_volume)
    updated_volume_from_manager = utils.get_ui_stack().music_audio_manager.get_volume()
    variables.config.set("music_volume", updated_volume_from_manager)


def on_sound_effects_volume_change(event):
    volume = event.GetEventObject().GetValue()
    adjusted_volume = volume * 5
    float_volume = adjusted_volume / 100
    utils.get_ui_stack().sound_effects_audio_manager.set_volume(float_volume)
    utils.get_ui_stack().sound_effects_audio_manager.play_audio("click.wav")
    updated_volume_from_manager = utils.get_ui_stack().sound_effects_audio_manager.get_volume()
    variables.config.set("sound_effects_volume", updated_volume_from_manager)

def on_rock_paper_scissors_bot_behavior_change(event):
    choice = event.GetEventObject().GetCurrentSelection()
    if choice == 0:
        variables.config.set("rock_paper_scissors_bot_behavior", "random")
    elif choice == 1:
        variables.config.set("rock_paper_scissors_bot_behavior", "rock")
    elif choice == 2:
        variables.config.set("rock_paper_scissors_bot_behavior", "paper")
    elif choice == 3:
        variables.config.set("rock_paper_scissors_bot_behavior", "scissors")

from game.card.ydke import Deck # noqa

@utils.ui_function
def help_menu_view():
    help_menu = VerticalMenu(_("Help"))
    help_menu.set_help_text(_("Help menu. Use the up and down arrow keys to navigate the menu, and press enter to select an option"))
    help_menu.append_item(_("Help"), None)
    help_menu.append_item(_("First time information"), lambda: first_ui_help_info(help_menu_view))
    help_menu.append_item(_("Back to main menu"), main_menu_view)
    return help_menu

@utils.ui_function
def make_windbot_deck():
    windbot_deck = VerticalMenu(_("Windbot deck"))
    name = windbot_deck.append_item(wx.TextCtrl, label=_("Deck name"))
    ydke_string = windbot_deck.append_item(wx.TextCtrl, label=_("Deck in YDKE format"))
    windbot_deck.append_item(_("Done"), lambda: save_windbot_deck(name.GetValue(), ydke_string.GetValue()))
    return windbot_deck

def save_windbot_deck(name, ydke_string):
        # if they are empty, go back to main menu
    if not name or not ydke_string:
        return main_menu_view()
    deck = Deck.from_ydke(ydke_string)
    # put it on the clipboard
    deck_data = deck.to_windbot_format()
    wx.TheClipboard.Open()
    wx.TheClipboard.SetData(wx.TextDataObject(deck_data))
    wx.TheClipboard.Close()
    sm = StatusMessage(_("Deck {name} has been saved to the clipboard").format(name=name), main_menu_view)
    sm.show()
    return

@utils.ui_function
def make_deck_string_from_windbot_deck():
    windbot_deck = VerticalMenu(_("Windbot deck"))
    name = windbot_deck.append_item(wx.TextCtrl, label=_("Deck name"))
    ydke_string = windbot_deck.append_item(wx.TextCtrl, label=_("Deck in Windbot format"))
    windbot_deck.append_item(_("Done"), lambda: save_deck_string_from_windbot_deck(name.GetValue(), ydke_string.GetValue()))
    return windbot_deck

def save_deck_string_from_windbot_deck(name, windbot_string):
    if not name or not windbot_string:
        return main_menu_view()
    deck = Deck.from_windbot_format(windbot_string)
    # put it on the clipboard
    deck_data = deck.to_ydke()
    wx.TheClipboard.Open()
    wx.TheClipboard.SetData(wx.TextDataObject(deck_data))
    wx.TheClipboard.Close()
    sm = StatusMessage(_("Deck {name} has been saved to the clipboard").format(name=name), main_menu_view)
    sm.show()
    return
