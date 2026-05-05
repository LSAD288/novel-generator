#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
烽火南境小说生成器 - KivyMD移动端完整版
包含所有核心功能：章节生成、改写、续写、AI痕迹消除、名字生成、书籍管理
"""

import os
import sys
import json
import threading

os.environ['KIVY_NO_ARGS'] = '1'
os.environ['KIVY_WINDOW'] = 'sdl2'
os.environ['KIVY_TEXT'] = 'sdl2'
os.environ['KIVY_IMAGE'] = 'sdl2'

from kivy.config import Config
Config.set('graphics', 'width', '360')
Config.set('graphics', 'height', '720')
Config.set('graphics', 'resizable', '0')
Config.set('kivy', 'exit_on_escape', '0')

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.spinner import Spinner
from kivy.uix.popup import Popup
from kivy.uix.progressbar import ProgressBar
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.floatlayout import FloatLayout

from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.card import MDCard
from kivymd.uix.button import MDRaisedButton, MDFlatButton, MDIconButton
from kivymd.uix.textfield import MDTextField
from kivymd.uix.label import MDLabel
from kivymd.uix.toolbar import MDTopAppBar
from kivymd.uix.tab import MDTabs, MDTabsBase
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.dialog import MDDialog
from kivymd.uix.progressbar import MDProgressBar
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.list import MDList, OneLineListItem, TwoLineListItem
from kivymd.uix.selectioncontrol import MDSwitch
from kivymd.uix.slider import MDSlider

from novel_core import (
    AIService,
    ConfigManager,
    BooksManager,
    GenreKnowledgeBase,
    AIHumanizer,
    get_module_status,
    get_books_manager,
    HAS_DYNAMIC_AI_HUMANIZER,
    HAS_ULTIMATE_AI_HUMANIZER,
    HAS_CHAPTER_PROMPT_HELPER,
    HAS_AUTHOR_MODELING,
    HAS_TOOLMAN_DETECTOR,
)


class TabBase(MDBoxLayout, MDTabsBase):
    pass


class NovelGeneratorApp(MDApp):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title = "烽火南境小说生成器"
        self.theme_cls.primary_palette = "Blue"
        self.theme_cls.theme_style = "Light"
        self.config_manager = ConfigManager()
        self.ai_service = AIService()
        self.books_manager = get_books_manager()
        self.genre_kb = GenreKnowledgeBase()
        self.dialog = None
        self.is_generating = False

        saved_api_key = self.config_manager.get_api_key()
        if saved_api_key:
            self.ai_service.set_api_key(saved_api_key)

    def build(self):
        Window.size = (360, 720)

        self.root_layout = MDBoxLayout(orientation='vertical')

        self.toolbar = MDTopAppBar(
            title="烽火南境小说生成器",
            elevation=4,
            pos_hint={'top': 1}
        )
        self.toolbar.left_action_items = [["menu", lambda x: self.open_nav_drawer()]]
        self.toolbar.right_action_items = [["cog", lambda x: self.switch_to_settings()]]
        self.root_layout.add_widget(self.toolbar)

        self.tabs = MDTabs()
        self.tabs.bind(on_tab_switch=self.on_tab_switch)

        self.tabs.add_widget(self._create_generate_tab())
        self.tabs.add_widget(self._create_rewrite_tab())
        self.tabs.add_widget(self._create_continue_tab())
        self.tabs.add_widget(self._create_names_tab())
        self.tabs.add_widget(self._create_ai_detect_tab())
        self.tabs.add_widget(self._create_books_tab())
        self.tabs.add_widget(self._create_settings_tab())

        self.root_layout.add_widget(self.tabs)

        self.status_bar = MDBoxLayout(
            size_hint_y=None,
            height=dp(30),
            md_bg_color=self.theme_cls.bg_darkest
        )
        self.status_label = MDLabel(
            text="就绪",
            theme_text_color="Secondary",
            size_hint_x=1,
            halign='center'
        )
        self.status_bar.add_widget(self.status_label)
        self.root_layout.add_widget(self.status_bar)

        return self.root_layout

    def _make_scroll_content(self):
        content = MDBoxLayout(orientation='vertical', padding=dp(12), spacing=dp(8), size_hint_y=None)
        content.bind(minimum_height=content.setter('height'))
        scroll = MDScrollView()
        scroll.add_widget(content)
        return scroll, content

    def _add_label(self, content, text):
        content.add_widget(MDLabel(text=text, size_hint_y=None, height=dp(28), font_style="Subtitle2"))

    def _add_spinner(self, content, text, values):
        spinner = Spinner(
            text=text,
            values=values,
            size_hint_y=None,
            height=dp(48),
            font_size=dp(14)
        )
        content.add_widget(spinner)
        return spinner

    def _add_text_input(self, content, hint, multiline=True, height=dp(120)):
        ti = TextInput(
            multiline=multiline,
            hint_text=hint,
            size_hint_y=None,
            height=height,
            font_size=dp(14)
        )
        content.add_widget(ti)
        return ti

    def _add_button(self, content, text, callback, disabled=False):
        btn = MDRaisedButton(
            text=text,
            size_hint=(1, None),
            height=dp(48),
            on_release=callback,
            disabled=disabled
        )
        content.add_widget(btn)
        return btn

    def _create_generate_tab(self):
        tab = TabBase(title="章节生成")
        scroll, content = self._make_scroll_content()

        self._add_label(content, "写作风格:")
        self.gen_style = self._add_spinner(content, '出版小说', [
            '出版小说', '网文', '霸道总裁', '玄幻', '仙侠', '都市',
            '历史', '科幻', '悬疑', '言情', '武侠', '奇幻',
            '恐怖', '网游', '末世', '轻小说', '剧本', '散文', '古风'
        ])

        self._add_label(content, "题材类型:")
        self.gen_genre = self._add_spinner(content, '都市情感', self.genre_kb.get_all_genres())

        self._add_label(content, "章节大纲:")
        self.gen_outline = self._add_text_input(content, "请输入章节大纲...")

        self._add_label(content, "详细细纲 (可选):")
        self.gen_detailed = self._add_text_input(content, "请输入详细细纲...", height=dp(90))

        self._add_label(content, "特殊要求 (可选):")
        self.gen_requirements = self._add_text_input(content, "请输入特殊要求...", height=dp(70))

        self._add_label(content, "AI痕迹消除强度:")
        self.gen_humanize_intensity = MDSlider(
            min=1, max=10, value=8,
            size_hint_y=None,
            height=dp(40)
        )
        content.add_widget(self.gen_humanize_intensity)

        self.gen_btn = self._add_button(content, "生成章节", self.do_generate_chapter)

        self._add_label(content, "生成结果:")
        self.gen_result = self._add_text_input(content, "生成的内容将显示在这里...", height=dp(250))

        result_btns = MDBoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        result_btns.add_widget(MDRaisedButton(text="复制结果", on_release=self.copy_gen_result, size_hint_x=0.5))
        result_btns.add_widget(MDRaisedButton(text="清空", on_release=self.clear_gen_result, size_hint_x=0.5))
        content.add_widget(result_btns)

        tab.add_widget(scroll)
        return tab

    def _create_rewrite_tab(self):
        tab = TabBase(title="改写")
        scroll, content = self._make_scroll_content()

        self._add_label(content, "改写风格:")
        self.rw_style = self._add_spinner(content, '出版小说', [
            '出版小说', '网文', '霸道总裁', '玄幻', '仙侠', '都市',
            '历史', '科幻', '悬疑', '言情', '武侠', '奇幻'
        ])

        self._add_label(content, "改写方向:")
        self.rw_direction = self._add_spinner(content, '文学润色', [
            '文学润色', '风格转换', '细节增强', '情感深化', '节奏优化', '语言精炼'
        ])

        self._add_label(content, "题材类型:")
        self.rw_genre = self._add_spinner(content, '都市情感', self.genre_kb.get_all_genres())

        self._add_label(content, "原文内容:")
        self.rw_original = self._add_text_input(content, "请输入需要改写的原文...", height=dp(180))

        self._add_label(content, "自定义要求 (可选):")
        self.rw_requirements = self._add_text_input(content, "请输入自定义改写要求...", height=dp(70))

        self.rw_btn = self._add_button(content, "开始改写", self.do_rewrite)

        self._add_label(content, "改写结果:")
        self.rw_result = self._add_text_input(content, "改写后的内容将显示在这里...", height=dp(250))

        result_btns = MDBoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        result_btns.add_widget(MDRaisedButton(text="复制结果", on_release=self.copy_rw_result, size_hint_x=0.5))
        result_btns.add_widget(MDRaisedButton(text="清空", on_release=self.clear_rw_result, size_hint_x=0.5))
        content.add_widget(result_btns)

        tab.add_widget(scroll)
        return tab

    def _create_continue_tab(self):
        tab = TabBase(title="续写")
        scroll, content = self._make_scroll_content()

        self._add_label(content, "续写风格:")
        self.ct_style = self._add_spinner(content, '出版小说', [
            '出版小说', '网文', '霸道总裁', '玄幻', '仙侠', '都市',
            '历史', '科幻', '悬疑', '言情', '武侠', '奇幻'
        ])

        self._add_label(content, "题材类型:")
        self.ct_genre = self._add_spinner(content, '都市情感', self.genre_kb.get_all_genres())

        self._add_label(content, "已有章节内容:")
        self.ct_existing = self._add_text_input(content, "请输入已有章节内容...", height=dp(180))

        self._add_label(content, "大纲 (可选):")
        self.ct_outline = self._add_text_input(content, "请输入大纲内容...", height=dp(90))

        self._add_label(content, "特殊要求 (可选):")
        self.ct_requirements = self._add_text_input(content, "请输入续写要求...", height=dp(70))

        self.ct_btn = self._add_button(content, "开始续写", self.do_continue)

        self._add_label(content, "续写结果:")
        self.ct_result = self._add_text_input(content, "续写的内容将显示在这里...", height=dp(250))

        result_btns = MDBoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        result_btns.add_widget(MDRaisedButton(text="复制结果", on_release=self.copy_ct_result, size_hint_x=0.5))
        result_btns.add_widget(MDRaisedButton(text="清空", on_release=self.clear_ct_result, size_hint_x=0.5))
        content.add_widget(result_btns)

        tab.add_widget(scroll)
        return tab

    def _create_names_tab(self):
        tab = TabBase(title="名字生成")
        scroll, content = self._make_scroll_content()

        self._add_label(content, "性别:")
        self.nm_gender = self._add_spinner(content, '男', ['男', '女'])

        self._add_label(content, "文化背景:")
        self.nm_country = self._add_spinner(content, '中国', [
            '中国', '日本', '韩国', '英国', '法国', '德国', '美国', '俄罗斯'
        ])

        self._add_label(content, "姓氏类型:")
        self.nm_surname_count = self._add_spinner(content, '单姓', ['单姓', '复姓'])

        self._add_label(content, "指定姓氏 (可选):")
        self.nm_surname = self._add_text_input(content, "留空则随机", multiline=False, height=dp(48))

        self._add_label(content, "指定名字 (可选):")
        self.nm_given = self._add_text_input(content, "留空则随机", multiline=False, height=dp(48))

        self._add_label(content, "特殊要求 (可选):")
        self.nm_requirements = self._add_text_input(content, "如：五行缺水、出自诗经...", height=dp(60))

        self.nm_btn = self._add_button(content, "生成名字", self.do_generate_names)

        self._add_label(content, "生成结果:")
        self.nm_result = self._add_text_input(content, "生成的名字将显示在这里...", height=dp(200))

        tab.add_widget(scroll)
        return tab

    def _create_ai_detect_tab(self):
        tab = TabBase(title="AI检测")
        scroll, content = self._make_scroll_content()

        self._add_label(content, "待检测文本:")
        self.detect_input = self._add_text_input(content, "请输入要检测AI痕迹的文本...", height=dp(200))

        self.detect_btn = self._add_button(content, "检测AI痕迹", self.do_detect_ai)

        self._add_label(content, "检测结果:")
        self.detect_result = self._add_text_input(content, "检测结果将显示在这里...", height=dp(150))

        self._add_label(content, "人性化处理:")
        self.humanize_intensity = MDSlider(
            min=1, max=10, value=8,
            size_hint_y=None,
            height=dp(40)
        )
        content.add_widget(self.humanize_intensity)

        self.humanize_btn = self._add_button(content, "人性化处理", self.do_humanize)

        self._add_label(content, "人性化结果:")
        self.humanize_result = self._add_text_input(content, "人性化处理后的文本将显示在这里...", height=dp(200))

        tab.add_widget(scroll)
        return tab

    def _create_books_tab(self):
        tab = TabBase(title="书籍管理")
        scroll, content = self._make_scroll_content()

        self._add_label(content, "新建书籍:")
        self.book_name = self._add_text_input(content, "请输入书籍名称...", multiline=False, height=dp(48))
        self.book_desc = self._add_text_input(content, "书籍描述 (可选)...", height=dp(60))

        self._add_button(content, "创建书籍", self.do_create_book)

        self._add_label(content, "已有书籍:")
        self.books_list = MDBoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(4))
        self.books_list.bind(minimum_height=self.books_list.setter('height'))
        content.add_widget(self.books_list)

        self._add_button(content, "刷新书籍列表", self.refresh_books_list)

        tab.add_widget(scroll)
        return tab

    def _create_settings_tab(self):
        tab = TabBase(title="设置")
        scroll, content = self._make_scroll_content()

        self._add_label(content, "DeepSeek API密钥:")
        self.api_key_input = TextInput(
            multiline=False,
            password=True,
            hint_text="请输入API密钥...",
            size_hint_y=None,
            height=dp(48),
            font_size=dp(14)
        )
        saved_key = self.config_manager.get_api_key()
        if saved_key:
            self.api_key_input.text = saved_key
        content.add_widget(self.api_key_input)

        self._add_button(content, "保存API密钥", self.save_api_key)

        self._add_label(content, "AI模型选择:")
        self.model_spinner = self._add_spinner(content, 'deepseek-reasoner', [
            'deepseek-reasoner', 'deepseek-chat'
        ])
        self.model_spinner.bind(text=self.on_model_change)

        self._add_label(content, "AI痕迹消除:")
        self.humanize_switch_layout = MDBoxLayout(size_hint_y=None, height=dp(40))
        self.humanize_switch_label = MDLabel(text="启用AI痕迹消除", size_hint_x=0.7)
        self.humanize_switch = MDSwitch(active=self.ai_service.humanize_enabled)
        self.humanize_switch.bind(active=self.on_humanize_switch)
        self.humanize_switch_layout.add_widget(self.humanize_switch_label)
        self.humanize_switch_layout.add_widget(self.humanize_switch)
        content.add_widget(self.humanize_switch_layout)

        self._add_label(content, "默认消除强度:")
        self.default_intensity = MDSlider(
            min=1, max=10, value=self.ai_service.humanize_intensity,
            size_hint_y=None,
            height=dp(40)
        )
        self.default_intensity.bind(value=self.on_default_intensity_change)
        content.add_widget(self.default_intensity)

        self._add_label(content, "模块状态:")
        module_status = get_module_status()
        status_text = ""
        for name, loaded in module_status.items():
            status_text += f"{'✅' if loaded else '❌'} {name}\n"
        self.module_status_label = MDLabel(
            text=status_text,
            size_hint_y=None,
            height=dp(180),
            font_style="Body2"
        )
        content.add_widget(self.module_status_label)

        self._add_label(content, "关于:")
        about_text = (
            "烽火南境小说生成器 v2.0.0\n\n"
            "基于AI的小说创作辅助工具\n"
            "支持章节生成、改写、续写、\n"
            "名字生成、AI痕迹消除等功能\n\n"
            "核心模块：\n"
            "- 题材知识库系统\n"
            "- AI痕迹抹除引擎\n"
            "- DeepSeek API集成\n"
            "- 书籍管理系统"
        )
        content.add_widget(MDLabel(
            text=about_text,
            size_hint_y=None,
            height=dp(180),
            font_style="Body2"
        ))

        tab.add_widget(scroll)
        return tab

    def on_tab_switch(self, instance_tabs, instance_tab, instance_tab_label, tab_text):
        self.status_label.text = f"当前: {tab_text}"

    def on_model_change(self, instance, value):
        self.ai_service.model = value

    def on_humanize_switch(self, instance, value):
        self.ai_service.set_humanizer_settings(enabled=value, intensity=self.ai_service.humanize_intensity)

    def on_default_intensity_change(self, instance, value):
        self.ai_service.set_humanizer_settings(
            enabled=self.ai_service.humanize_enabled,
            intensity=int(value)
        )

    def switch_to_settings(self):
        self.tabs.switch_tab("设置")

    def open_nav_drawer(self):
        pass

    def set_status(self, text):
        self.status_label.text = text

    def show_dialog(self, title, text):
        if self.dialog:
            self.dialog.dismiss()
        self.dialog = MDDialog(
            title=title,
            text=text,
            buttons=[MDFlatButton(text="确定", on_release=lambda x: self.dialog.dismiss())]
        )
        self.dialog.open()

    def _run_async(self, func, callback, *args):
        def worker():
            try:
                result = func(*args)
                Clock.schedule_once(lambda dt: callback(result), 0)
            except Exception as e:
                error_msg = f"操作出错: {str(e)}"
                Clock.schedule_once(lambda dt: callback(error_msg), 0)
            finally:
                self.is_generating = False
                Clock.schedule_once(lambda dt: self._enable_buttons(), 0)

        self.is_generating = True
        self._disable_buttons()
        threading.Thread(target=worker, daemon=True).start()

    def _disable_buttons(self):
        for attr in ['gen_btn', 'rw_btn', 'ct_btn', 'nm_btn', 'detect_btn', 'humanize_btn']:
            if hasattr(self, attr):
                getattr(self, attr).disabled = True

    def _enable_buttons(self):
        for attr in ['gen_btn', 'rw_btn', 'ct_btn', 'nm_btn', 'detect_btn', 'humanize_btn']:
            if hasattr(self, attr):
                getattr(self, attr).disabled = False

    def do_generate_chapter(self, instance):
        outline = self.gen_outline.text.strip()
        if not outline:
            self.show_dialog("提示", "请输入章节大纲")
            return

        genre = self.gen_genre.text
        style = self.gen_style.text
        detailed = self.gen_detailed.text.strip()
        requirements = self.gen_requirements.text.strip()
        intensity = int(self.gen_humanize_intensity.value)

        self.ai_service.set_humanizer_settings(
            enabled=self.ai_service.humanize_enabled,
            intensity=intensity
        )

        self.set_status("正在生成章节...")
        self.gen_result.text = "正在生成中，请稍候..."

        def on_result(result):
            self.gen_result.text = result
            self.set_status("章节生成完成")

        self._run_async(
            self.ai_service.generate_chapter,
            on_result,
            outline, detailed, requirements, genre, style
        )

    def do_rewrite(self, instance):
        original = self.rw_original.text.strip()
        if not original:
            self.show_dialog("提示", "请输入需要改写的原文")
            return

        style = self.rw_style.text
        direction = self.rw_direction.text
        genre = self.rw_genre.text
        requirements = self.rw_requirements.text.strip()

        self.set_status("正在改写...")
        self.rw_result.text = "正在改写中，请稍候..."

        def on_result(result):
            self.rw_result.text = result
            self.set_status("改写完成")

        self._run_async(
            self.ai_service.rewrite_content,
            on_result,
            original, style, direction, requirements, genre
        )

    def do_continue(self, instance):
        existing = self.ct_existing.text.strip()
        if not existing:
            self.show_dialog("提示", "请输入已有章节内容")
            return

        style = self.ct_style.text
        genre = self.ct_genre.text
        outline = self.ct_outline.text.strip()
        requirements = self.ct_requirements.text.strip()

        self.set_status("正在续写...")
        self.ct_result.text = "正在续写中，请稍候..."

        def on_result(result):
            self.ct_result.text = result
            self.set_status("续写完成")

        self._run_async(
            self.ai_service.continue_content,
            on_result,
            existing, outline, requirements, genre, style
        )

    def do_generate_names(self, instance):
        gender = self.nm_gender.text
        country = self.nm_country.text
        surname_count = self.nm_surname_count.text
        surname = self.nm_surname.text.strip()
        given_name = self.nm_given.text.strip()
        requirements = self.nm_requirements.text.strip()

        self.set_status("正在生成名字...")
        self.nm_result.text = "正在生成中，请稍候..."

        def on_result(result):
            self.nm_result.text = result
            self.set_status("名字生成完成")

        self._run_async(
            self.ai_service.generate_names,
            on_result,
            gender, country, surname_count, surname, given_name, requirements
        )

    def do_detect_ai(self, instance):
        text = self.detect_input.text.strip()
        if not text:
            self.show_dialog("提示", "请输入要检测的文本")
            return

        result = self.ai_service.detect_ai_score(text)
        result_text = (
            f"AI概率: {result.get('ai_probability', 0)}%\n"
            f"等级: {result.get('grade', '未知')}\n"
            f"建议: {result.get('recommendation', '无')}\n"
        )
        if result.get('reasons'):
            result_text += "\n检测到的问题:\n"
            for reason in result['reasons']:
                result_text += f"  • {reason}\n"

        self.detect_result.text = result_text
        self.set_status("AI检测完成")

    def do_humanize(self, instance):
        text = self.detect_input.text.strip()
        if not text:
            self.show_dialog("提示", "请输入要处理的文本")
            return

        intensity = int(self.humanize_intensity.value)
        self.ai_service.set_humanizer_settings(
            enabled=True,
            intensity=intensity
        )

        self.set_status("正在进行人性化处理...")
        self.humanize_result.text = "正在处理中，请稍候..."

        def on_result(result):
            self.humanize_result.text = result
            self.set_status("人性化处理完成")

        self._run_async(
            self.ai_service.humanize_content,
            on_result,
            text, intensity
        )

    def do_create_book(self, instance):
        name = self.book_name.text.strip()
        if not name:
            self.show_dialog("提示", "请输入书籍名称")
            return

        desc = self.book_desc.text.strip()
        book_id = self.books_manager.create_book(name, description=desc)
        self.show_dialog("成功", f"书籍 '{name}' 创建成功！\nID: {book_id}")
        self.book_name.text = ""
        self.book_desc.text = ""
        self.refresh_books_list(None)

    def refresh_books_list(self, instance):
        self.books_list.clear_widgets()
        books = self.books_manager.get_all_books()
        if not books:
            self.books_list.add_widget(MDLabel(text="暂无书籍", size_hint_y=None, height=dp(30)))
            return

        for book_id, book_info in books.items():
            item = TwoLineListItem(
                text=book_info.get('name', '未命名'),
                secondary_text=f"创建: {book_info.get('created_at', '未知')}",
                on_release=lambda x, bid=book_id: self.select_book(bid)
            )
            self.books_list.add_widget(item)

    def select_book(self, book_id):
        self.books_manager.set_current_book(book_id)
        book_info = self.books_manager.get_book_info(book_id)
        name = book_info.get('name', '未命名') if book_info else '未知'
        self.set_status(f"当前书籍: {name}")
        self.show_dialog("选择书籍", f"已选择书籍: {name}")

    def save_api_key(self, instance):
        api_key = self.api_key_input.text.strip()
        if not api_key:
            self.show_dialog("提示", "请输入API密钥")
            return

        self.config_manager.save_api_key(api_key)
        self.ai_service.set_api_key(api_key)
        self.show_dialog("成功", "API密钥已保存")

    def copy_gen_result(self, instance):
        self._copy_to_clipboard(self.gen_result.text)

    def copy_rw_result(self, instance):
        self._copy_to_clipboard(self.rw_result.text)

    def copy_ct_result(self, instance):
        self._copy_to_clipboard(self.ct_result.text)

    def clear_gen_result(self, instance):
        self.gen_result.text = ""

    def clear_rw_result(self, instance):
        self.rw_result.text = ""

    def clear_ct_result(self, instance):
        self.ct_result.text = ""

    def _copy_to_clipboard(self, text):
        if text and not text.startswith("正在") and not text.startswith("生成的内容"):
            try:
                from kivy.core.clipboard import Clipboard
                Clipboard.copy(text)
                self.set_status("已复制到剪贴板")
            except Exception:
                self.set_status("复制失败")


if __name__ == '__main__':
    NovelGeneratorApp().run()
