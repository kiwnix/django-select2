import json
import os
from collections.abc import Iterable

import pytest
from django.db.models import QuerySet
from django.urls import reverse
from django.utils import translation
from django.utils.encoding import force_str
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait

from django_select2.cache import cache
from django_select2.forms import (
    HeavySelect2MultipleWidget,
    HeavySelect2Widget,
    ModelSelect2TagWidget,
    ModelSelect2Widget,
    Select2AdminMixin,
    Select2Widget,
)
from tests.testapp import forms
from tests.testapp.forms import (
    NUMBER_CHOICES,
    HeavySelect2MultipleWidgetForm,
    TitleModelSelect2Widget,
)
from tests.testapp.models import Artist, City, Country, Genre, Groupie


class TestSelect2Mixin:
    url = reverse("select2_widget")
    form = forms.AlbumSelect2WidgetForm()
    multiple_form = forms.AlbumSelect2MultipleWidgetForm()
    widget_cls = Select2Widget

    def test_initial_data(self, genres):
        genre = genres[0]
        form = self.form.__class__(initial={"primary_genre": genre.pk})
        assert str(genre) in form.as_p()

    def test_initial_form_class(self):
        widget = self.widget_cls(attrs={"class": "my-class"})
        assert "my-class" in widget.render("name", None)
        assert "django-select2" in widget.render("name", None)

    def test_lang_attr(self):
        with translation.override("de"):
            widget = Select2Widget()
            assert 'lang="de"' in widget.render("name", None)

        # Regression test for #163
        widget = Select2Widget()
        assert widget.i18n_name == "en"
        with translation.override("de"):
            assert widget.i18n_name == "de"

    def test_allow_clear(self, db):
        required_field = self.form.fields["artist"]
        assert required_field.required is True
        assert 'data-allow-clear="true"' not in required_field.widget.render(
            "artist", None
        )
        assert 'data-allow-clear="false"' in required_field.widget.render(
            "artist", None
        )
        assert '<option value=""></option>' not in required_field.widget.render(
            "artist", None
        )

        not_required_field = self.form.fields["primary_genre"]
        assert not_required_field.required is False
        assert 'data-allow-clear="true"' in not_required_field.widget.render(
            "primary_genre", None
        )
        assert 'data-allow-clear="false"' not in not_required_field.widget.render(
            "primary_genre", None
        )
        assert "data-placeholder" in not_required_field.widget.render(
            "primary_genre", None
        )
        assert '<option value=""></option>' in not_required_field.widget.render(
            "primary_genre", None
        )

    @pytest.mark.selenium
    def test_no_js_error(self, db, live_server, driver):
        driver.get(live_server + self.url)
        with pytest.raises(NoSuchElementException):
            error = driver.find_element(By.XPATH, "//body[@JSError]")
            pytest.fail(error.get_attribute("JSError"))

    @pytest.mark.selenium
    def test_selecting(self, db, live_server, driver):
        driver.get(live_server + self.url)
        with pytest.raises(NoSuchElementException):
            driver.find_element(By.CSS_SELECTOR, ".select2-results")
        elem = driver.find_element(By.CSS_SELECTOR, ".select2-selection")
        elem.click()
        results = driver.find_element(By.CSS_SELECTOR, ".select2-results")
        assert results.is_displayed() is True
        elem = results.find_element(By.CSS_SELECTOR, ".select2-results__option")
        elem.click()

        with pytest.raises(NoSuchElementException):
            error = driver.find_element(By.XPATH, "//body[@JSError]")
            pytest.fail(error.get_attribute("JSError"))

    def test_data_url(self):
        with pytest.raises(ValueError):
            HeavySelect2Widget()

        widget = HeavySelect2Widget(data_url="/foo/bar")
        assert widget.get_url() == "/foo/bar"

    def test_empty_option(self, db):
        # Empty options is only required for single selects
        # https://select2.github.io/options.html#allowClear
        single_select = self.form.fields["primary_genre"]
        assert single_select.required is False
        assert '<option value=""></option>' in single_select.widget.render(
            "primary_genre", None
        )

        multiple_select = self.multiple_form.fields["featured_artists"]
        assert multiple_select.required is False
        assert multiple_select.widget.allow_multiple_selected
        output = multiple_select.widget.render("featured_artists", None)
        assert '<option value=""></option>' not in output
        assert 'data-placeholder=""' in output

    def test_i18n(self):
        translation.activate("de")
        assert tuple(Select2Widget().media._js) == (
            "admin/js/vendor/select2/select2.full.min.js",
            "admin/js/vendor/select2/i18n/de.js",
            "django_select2/django_select2.js",
        )

        translation.activate("en")
        assert tuple(Select2Widget().media._js) == (
            "admin/js/vendor/select2/select2.full.min.js",
            "admin/js/vendor/select2/i18n/en.js",
            "django_select2/django_select2.js",
        )

        translation.activate("00")
        assert tuple(Select2Widget().media._js) == (
            "admin/js/vendor/select2/select2.full.min.js",
            "django_select2/django_select2.js",
        )

        translation.activate("sr-Cyrl")
        assert tuple(Select2Widget().media._js) == (
            "admin/js/vendor/select2/select2.full.min.js",
            "admin/js/vendor/select2/i18n/sr-Cyrl.js",
            "django_select2/django_select2.js",
        )

        pytest.importorskip("django", minversion="2.0.4")

        translation.activate("zh-hans")
        assert tuple(Select2Widget().media._js) == (
            "admin/js/vendor/select2/select2.full.min.js",
            "admin/js/vendor/select2/i18n/zh-CN.js",
            "django_select2/django_select2.js",
        )

        translation.activate("zh-hant")
        assert tuple(Select2Widget().media._js) == (
            "admin/js/vendor/select2/select2.full.min.js",
            "admin/js/vendor/select2/i18n/zh-TW.js",
            "django_select2/django_select2.js",
        )

    def test_theme_setting(self, settings):
        settings.SELECT2_THEME = "classic"
        widget = self.widget_cls()
        assert 'data-theme="classic"' in widget.render("name", None)


class TestSelect2AdminMixin:
    def test_media(self):
        translation.activate("en")
        assert tuple(Select2AdminMixin().media._js) == (
            "admin/js/vendor/select2/select2.full.min.js",
            "admin/js/vendor/select2/i18n/en.js",
            "admin/js/jquery.init.js",
            "django_select2/django_select2.js",
        )

        assert dict(Select2AdminMixin().media._css) == {
            "screen": [
                "admin/css/vendor/select2/select2.min.css",
                "admin/css/autocomplete.css",
                "django_select2/django_select2.css",
            ]
        }


class TestSelect2MixinSettings:
    def test_default_media(self):
        sut = Select2Widget()
        result = sut.media.render()
        assert "admin/js/vendor/select2/select2.full.min.js" in result
        assert "admin/css/vendor/select2/select2.min.css" in result
        assert "django_select2/django_select2.js" in result

    def test_js_setting(self, settings):
        settings.SELECT2_JS = "alternate.js"
        sut = Select2Widget()
        result = sut.media.render()
        assert "alternate.js" in result
        assert "django_select2/django_select2.js" in result

    def test_empty_js_setting(self, settings):
        settings.SELECT2_JS = ""
        sut = Select2Widget()
        result = sut.media.render()
        assert "django_select2/django_select2.js" in result

    def test_css_setting(self, settings):
        settings.SELECT2_CSS = "alternate.css"
        sut = Select2Widget()
        result = sut.media.render()
        assert "alternate.css" in result

    def test_empty_css_setting(self, settings):
        settings.SELECT2_CSS = ""
        sut = Select2Widget()
        result = sut.media.render()
        assert "/select2.css" not in result

    def test_multiple_css_setting(self, settings):
        settings.SELECT2_CSS = ["select2.css", "select2-theme.css"]
        sut = Select2Widget()
        result = sut.media.render()
        assert "select2.css" in result
        assert "select2-theme.css" in result


class TestHeavySelect2Mixin(TestSelect2Mixin):
    url = reverse("heavy_select2_widget")
    form = forms.HeavySelect2WidgetForm(initial={"primary_genre": 1})
    widget_cls = HeavySelect2Widget

    def test_initial_data(self):
        assert "One" in self.form.as_p()

    def test_initial_form_class(self):
        widget = self.widget_cls(data_view="heavy_data_1", attrs={"class": "my-class"})
        assert "my-class" in widget.render("name", None)
        assert "django-select2" in widget.render("name", None)
        assert "django-select2-heavy" in widget.render("name", None), widget.render(
            "name", None
        )

    def test_lang_attr(self):
        with translation.override("fr"):
            widget = self.widget_cls(data_view="heavy_data_1")
            assert 'lang="fr"' in widget.render("name", None)

    def test_selected_option(self, db):
        not_required_field = self.form.fields["primary_genre"]
        assert not_required_field.required is False
        assert (
            '<option value="1" selected="selected">One</option>'
            in not_required_field.widget.render("primary_genre", 1)
            or '<option value="1" selected>One</option>'
            in not_required_field.widget.render("primary_genre", 1)
        ), not_required_field.widget.render(
            "primary_genre", 1
        )

    def test_many_selected_option(self, db, genres):
        field = HeavySelect2MultipleWidgetForm().fields["genres"]
        field.widget.choices = NUMBER_CHOICES
        widget_output = field.widget.render("genres", [1, 2])
        selected_option = (
            '<option value="{pk}" selected="selected">{value}</option>'.format(
                pk=1, value="One"
            )
        )
        selected_option_a = '<option value="{pk}" selected>{value}</option>'.format(
            pk=1, value="One"
        )
        selected_option2 = (
            '<option value="{pk}" selected="selected">{value}</option>'.format(
                pk=2, value="Two"
            )
        )
        selected_option2a = '<option value="{pk}" selected>{value}</option>'.format(
            pk=2, value="Two"
        )

        assert (
            selected_option in widget_output or selected_option_a in widget_output
        ), widget_output
        assert selected_option2 in widget_output or selected_option2a in widget_output

    @pytest.mark.selenium
    def test_multiple_widgets(self, db, live_server, driver):
        driver.get(live_server + self.url)
        with pytest.raises(NoSuchElementException):
            driver.find_element(By.CSS_SELECTOR, ".select2-results")

        elem1, elem2 = driver.find_elements(By.CSS_SELECTOR, ".select2-selection")

        elem1.click()
        search1 = driver.find_element(By.CSS_SELECTOR, ".select2-search__field")
        search1.send_keys("fo")
        result1 = (
            WebDriverWait(driver, 60)
            .until(
                expected_conditions.presence_of_element_located(
                    (By.CSS_SELECTOR, ".select2-results li:first-child")
                )
            )
            .text
        )

        elem2.click()
        search2 = driver.find_element(By.CSS_SELECTOR, ".select2-search__field")
        search2.send_keys("fo")
        result2 = (
            WebDriverWait(driver, 60)
            .until(
                expected_conditions.presence_of_element_located(
                    (By.CSS_SELECTOR, ".select2-results li:first-child")
                )
            )
            .text
        )

        assert result1 != result2

        with pytest.raises(NoSuchElementException):
            error = driver.find_element(By.XPATH, "//body[@JSError]")
            pytest.fail(error.get_attribute("JSError"))

    def test_get_url(self):
        widget = self.widget_cls(data_view="heavy_data_1", attrs={"class": "my-class"})
        assert isinstance(widget.get_url(), str)

    def test_can_not_pickle(self):
        widget = self.widget_cls(data_view="heavy_data_1", attrs={"class": "my-class"})

        class NoPickle:
            pass

        widget.no_pickle = NoPickle()
        with pytest.raises(NotImplementedError):
            widget.set_to_cache()

    def test_theme_setting(self, settings):
        settings.SELECT2_THEME = "classic"
        widget = self.widget_cls(data_view="heavy_data_1")
        assert 'data-theme="classic"' in widget.render("name", None)

    def test_cache_key_leak(self):
        bob = self.widget_cls(data_url="/test/")
        alice = self.widget_cls(data_url="/test/")
        bob.render("name", "value")
        bob_key_request_1 = bob._get_cache_key()
        alice.render("name", "value")
        assert bob._get_cache_key() != alice._get_cache_key()
        bob.render("name", "value")
        bob_key_request_2 = bob._get_cache_key()
        assert bob_key_request_1 != bob_key_request_2


class TestModelSelect2Mixin(TestHeavySelect2Mixin):
    form = forms.AlbumModelSelect2WidgetForm(initial={"primary_genre": 1})
    multiple_form = forms.ArtistModelSelect2MultipleWidgetForm()

    def test_initial_data(self, genres):
        genre = genres[0]
        form = self.form.__class__(initial={"primary_genre": genre.pk})
        assert str(genre) in form.as_p()

    def test_label_from_instance_initial(self, genres):
        genre = genres[0]
        genre.title = genre.title.lower()
        genre.save()

        form = self.form.__class__(initial={"primary_genre": genre.pk})
        assert genre.title not in form.as_p(), form.as_p()
        assert genre.title.upper() in form.as_p()

    @pytest.fixture(autouse=True)
    def genres(self, genres):
        return genres

    def test_selected_option(self, db, genres):
        genre = genres[0]
        genre2 = genres[1]
        not_required_field = self.form.fields["primary_genre"]
        assert not_required_field.required is False
        widget_output = not_required_field.widget.render("primary_genre", genre.pk)
        selected_option = (
            '<option value="{pk}" selected="selected">{value}</option>'.format(
                pk=genre.pk, value=force_str(genre)
            )
        )
        selected_option_a = '<option value="{pk}" selected>{value}</option>'.format(
            pk=genre.pk, value=force_str(genre)
        )
        unselected_option = '<option value="{pk}">{value}</option>'.format(
            pk=genre2.pk, value=force_str(genre2)
        )

        assert (
            selected_option in widget_output or selected_option_a in widget_output
        ), widget_output
        assert unselected_option not in widget_output

    def test_selected_option_label_from_instance(self, db, genres):
        genre = genres[0]
        genre.title = genre.title.lower()
        genre.save()

        field = self.form.fields["primary_genre"]
        widget_output = field.widget.render("primary_genre", genre.pk)

        def get_selected_options(genre):
            return (
                '<option value="{pk}" selected="selected">{value}</option>'.format(
                    pk=genre.pk, value=force_str(genre)
                ),
                '<option value="{pk}" selected>{value}</option>'.format(
                    pk=genre.pk, value=force_str(genre)
                ),
            )

        assert all(o not in widget_output for o in get_selected_options(genre))
        genre.title = genre.title.upper()

        assert any(o in widget_output for o in get_selected_options(genre))

    def test_get_queryset(self):
        widget = ModelSelect2Widget()
        with pytest.raises(NotImplementedError):
            widget.get_queryset()
        widget.model = Genre
        assert isinstance(widget.get_queryset(), QuerySet)
        widget.model = None
        widget.queryset = Genre.objects.all()
        assert isinstance(widget.get_queryset(), QuerySet)

    def test_result_from_instance_ModelSelect2Widget(self, genres):
        widget = ModelSelect2Widget()
        widget.model = Genre
        genre = Genre.objects.first()
        assert widget.result_from_instance(genre, request=None) == {
            "id": genre.pk,
            "text": str(genre),
        }

    def test_tag_attrs_Select2Widget(self):
        widget = Select2Widget()
        output = widget.render("name", "value")
        assert 'data-minimum-input-length="0"' in output

    def test_custom_tag_attrs_Select2Widget(self):
        widget = Select2Widget(attrs={"data-minimum-input-length": "3"})
        output = widget.render("name", "value")
        assert 'data-minimum-input-length="3"' in output

    def test_tag_attrs_ModelSelect2Widget(self):
        widget = ModelSelect2Widget(
            queryset=Genre.objects.all(), search_fields=["title__icontains"]
        )
        output = widget.render("name", "value")
        assert 'data-minimum-input-length="2"' in output

    def test_tag_attrs_ModelSelect2TagWidget(self):
        widget = ModelSelect2TagWidget(
            queryset=Genre.objects.all(), search_fields=["title__icontains"]
        )
        output = widget.render("name", "value")
        assert 'data-minimum-input-length="2"' in output

    def test_tag_attrs_HeavySelect2Widget(self):
        widget = HeavySelect2Widget(data_url="/foo/bar/")
        output = widget.render("name", "value")
        assert 'data-minimum-input-length="2"' in output

    def test_custom_tag_attrs_ModelSelect2Widget(self):
        widget = ModelSelect2Widget(
            queryset=Genre.objects.all(),
            search_fields=["title__icontains"],
            attrs={"data-minimum-input-length": "3"},
        )
        output = widget.render("name", "value")
        assert 'data-minimum-input-length="3"' in output

    def test_get_search_fields(self):
        widget = ModelSelect2Widget()
        with pytest.raises(NotImplementedError):
            widget.get_search_fields()

        widget.search_fields = ["title__icontains"]
        assert isinstance(widget.get_search_fields(), Iterable)
        assert all(isinstance(x, str) for x in widget.get_search_fields())

    def test_filter_queryset(self, genres):
        widget = TitleModelSelect2Widget(queryset=Genre.objects.all())
        assert widget.filter_queryset(None, genres[0].title[:3]).exists()

        widget = TitleModelSelect2Widget(
            search_fields=["title__icontains"], queryset=Genre.objects.all()
        )
        qs = widget.filter_queryset(
            None, " ".join([genres[0].title[:3], genres[0].title[3:]])
        )
        assert qs.exists()

    def test_filter_queryset__empty(self, genres):
        widget = TitleModelSelect2Widget(queryset=Genre.objects.all())
        assert widget.filter_queryset(None, genres[0].title[:3]).exists()

        widget = TitleModelSelect2Widget(
            search_fields=["title__icontains"], queryset=Genre.objects.all()
        )
        qs = widget.filter_queryset(None, "")
        assert qs.exists()

    def test_filter_queryset__startswith(self, genres):
        genre = Genre.objects.create(title="Space Genre")
        widget = TitleModelSelect2Widget(queryset=Genre.objects.all())
        assert widget.filter_queryset(None, genre.title).exists()

        widget = TitleModelSelect2Widget(
            search_fields=["title__istartswith"], queryset=Genre.objects.all()
        )
        qs = widget.filter_queryset(None, "Space Gen")
        assert qs.exists()

        qs = widget.filter_queryset(None, "Gen")
        assert not qs.exists()

    def test_filter_queryset__contains(self, genres):
        genre = Genre.objects.create(title="Space Genre")
        widget = TitleModelSelect2Widget(queryset=Genre.objects.all())
        assert widget.filter_queryset(None, genre.title).exists()

        widget = TitleModelSelect2Widget(
            search_fields=["title__contains"], queryset=Genre.objects.all()
        )
        qs = widget.filter_queryset(None, "Space Gen")
        assert qs.exists()

        qs = widget.filter_queryset(None, "NOT Gen")
        assert not qs.exists(), "contains works even if all bits match"

    def test_filter_queryset__multiple_fields(self, genres):
        genre = Genre.objects.create(title="Space Genre")
        widget = TitleModelSelect2Widget(queryset=Genre.objects.all())
        assert widget.filter_queryset(None, genre.title).exists()

        widget = TitleModelSelect2Widget(
            search_fields=[
                "title__startswith",
                "title__endswith",
            ],
            queryset=Genre.objects.all(),
        )
        qs = widget.filter_queryset(None, "Space")
        assert qs.exists()

        qs = widget.filter_queryset(None, "Genre")
        assert qs.exists()

    def test_model_kwarg(self):
        widget = ModelSelect2Widget(model=Genre, search_fields=["title__icontains"])
        genre = Genre.objects.last()
        result = widget.filter_queryset(None, genre.title)
        assert result.exists()

    def test_queryset_kwarg(self):
        widget = ModelSelect2Widget(
            queryset=Genre.objects.all(), search_fields=["title__icontains"]
        )
        genre = Genre.objects.last()
        result = widget.filter_queryset(None, genre.title)
        assert result.exists()

    def test_ajax_view_registration(self, client):
        widget = ModelSelect2Widget(
            queryset=Genre.objects.all(), search_fields=["title__icontains"]
        )
        widget.render("name", "value")
        url = reverse("django_select2:auto-json")
        genre = Genre.objects.last()
        response = client.get(
            url, data=dict(field_id=widget.field_id, term=genre.title)
        )
        assert response.status_code == 200, response.content
        data = json.loads(response.content.decode("utf-8"))
        assert data["results"]
        assert genre.pk in [result["id"] for result in data["results"]]

    def test_render(self):
        widget = ModelSelect2Widget(queryset=Genre.objects.all())
        widget.render("name", "value")
        cached_widget = cache.get(widget._get_cache_key())
        assert cached_widget["max_results"] == widget.max_results
        assert cached_widget["search_fields"] == tuple(widget.search_fields)
        qs = widget.get_queryset()
        assert isinstance(cached_widget["queryset"][0], qs.__class__)
        assert str(cached_widget["queryset"][1]) == str(qs.query)

    def test_get_url(self):
        widget = ModelSelect2Widget(
            queryset=Genre.objects.all(), search_fields=["title__icontains"]
        )
        assert isinstance(widget.get_url(), str)

    def test_custom_to_field_name(self):
        the_best_band_in_the_world = Artist.objects.create(title="Take That")
        groupie = Groupie.objects.create(obsession=the_best_band_in_the_world)
        form = forms.GroupieForm(instance=groupie)
        assert '<option value="Take That" selected>TAKE THAT</option>' in form.as_p()

    def test_empty_label(self, db):
        # Empty options is only required for single selects
        # https://select2.github.io/options.html#allowClear
        single_select = self.form.fields["primary_genre"]
        single_select.empty_label = "Hello World"
        assert single_select.required is False
        assert 'data-placeholder="Hello World"' in single_select.widget.render(
            "primary_genre", None
        )


class TestHeavySelect2TagWidget(TestHeavySelect2Mixin):
    def test_tag_attrs(self):
        widget = ModelSelect2TagWidget(
            queryset=Genre.objects.all(), search_fields=["title__icontains"]
        )
        output = widget.render("name", "value")
        assert 'data-minimum-input-length="2"' in output
        assert 'data-tags="true"' in output
        assert "data-token-separators" in output

    def test_custom_tag_attrs(self):
        widget = ModelSelect2TagWidget(
            queryset=Genre.objects.all(),
            search_fields=["title__icontains"],
            attrs={"data-minimum-input-length": "3"},
        )
        output = widget.render("name", "value")
        assert 'data-minimum-input-length="3"' in output


class TestHeavySelect2MultipleWidget:
    url = reverse("heavy_select2_multiple_widget")
    form = forms.HeavySelect2MultipleWidgetForm()
    widget_cls = HeavySelect2MultipleWidget

    @pytest.mark.xfail(
        bool(os.environ.get("CI", False)),
        reason="https://bugs.chromium.org/p/chromedriver/issues/detail?id=1772",
    )
    @pytest.mark.selenium
    def test_widgets_selected_after_validation_error(self, db, live_server, driver):
        driver.get(live_server + self.url)
        WebDriverWait(driver, 3).until(
            expected_conditions.presence_of_element_located((By.ID, "id_title"))
        )
        title = driver.find_element(By.ID, "id_title")
        title.send_keys("fo")
        genres, fartists = driver.find_elements(
            By.CSS_SELECTOR, ".select2-selection--multiple"
        )
        genres.click()
        genres.send_keys("o")  # results are Zero One Two Four
        # select second element - One
        driver.find_element(By.CSS_SELECTOR, ".select2-results li:nth-child(2)").click()
        genres.submit()
        # there is a ValidationError raised, check for it
        errstring = (
            WebDriverWait(driver, 3)
            .until(
                expected_conditions.presence_of_element_located(
                    (By.CSS_SELECTOR, "ul.errorlist li")
                )
            )
            .text
        )
        assert errstring == "Title must have more than 3 characters."
        # genres should still have One as selected option
        result_title = driver.find_element(
            By.CSS_SELECTOR, ".select2-selection--multiple li"
        ).get_attribute("title")
        assert result_title == "One"


class TestAddressChainedSelect2Widget:
    url = reverse("model_chained_select2_widget")
    form = forms.AddressChainedSelect2WidgetForm()

    @pytest.mark.selenium
    def test_widgets_selected_after_validation_error(
        self, db, live_server, driver, countries, cities
    ):
        driver.get(live_server + self.url)

        WebDriverWait(driver, 60).until(
            expected_conditions.presence_of_element_located(
                (By.CSS_SELECTOR, ".select2-selection--single")
            )
        )
        (
            country_container,
            city_container,
            city2_container,
        ) = driver.find_elements(By.CSS_SELECTOR, ".select2-selection--single")

        # clicking city select2 lists all available cities
        city_container.click()
        WebDriverWait(driver, 60).until(
            expected_conditions.presence_of_element_located(
                (By.CSS_SELECTOR, ".select2-results li")
            )
        )
        city_options = driver.find_elements(By.CSS_SELECTOR, ".select2-results li")
        city_names_from_browser = {option.text for option in city_options}
        city_names_from_db = set(City.objects.values_list("name", flat=True))
        assert len(city_names_from_browser) == City.objects.count()
        assert city_names_from_browser == city_names_from_db

        # selecting a country really does it
        country_container.click()
        WebDriverWait(driver, 60).until(
            expected_conditions.presence_of_element_located(
                (By.CSS_SELECTOR, ".select2-results li:nth-child(2)")
            )
        )
        country_option = driver.find_element(
            By.CSS_SELECTOR, ".select2-results li:nth-child(2)"
        )
        country_name = country_option.text
        country_option.click()
        assert country_name == country_container.text

        # clicking city select2 lists reduced list of cities belonging to the country
        city_container.click()
        WebDriverWait(driver, 60).until(
            expected_conditions.presence_of_element_located(
                (By.CSS_SELECTOR, ".select2-results li")
            )
        )
        city_options = driver.find_elements(By.CSS_SELECTOR, ".select2-results li")
        city_names_from_browser = {option.text for option in city_options}
        city_names_from_db = set(
            Country.objects.get(name=country_name).cities.values_list("name", flat=True)
        )
        assert len(city_names_from_browser) != City.objects.count()
        assert city_names_from_browser == city_names_from_db

        # selecting a city really does it
        city_option = driver.find_element(
            By.CSS_SELECTOR, ".select2-results li:nth-child(2)"
        )
        city_name = city_option.text
        city_option.click()
        assert city_name == city_container.text

        # clicking country select2 lists reduced list to the only country available to the city
        country_container.click()
        WebDriverWait(driver, 60).until(
            expected_conditions.presence_of_element_located(
                (By.CSS_SELECTOR, ".select2-results li")
            )
        )
        country_options = driver.find_elements(By.CSS_SELECTOR, ".select2-results li")
        country_names_from_browser = {option.text for option in country_options}
        country_names_from_db = {City.objects.get(name=city_name).country.name}
        assert len(country_names_from_browser) != Country.objects.count()
        assert country_names_from_browser == country_names_from_db

    @pytest.mark.selenium
    def test_dependent_fields_clear_after_change_parent(
        self, db, live_server, driver, countries, cities
    ):
        driver.get(live_server + self.url)
        (
            country_container,
            city_container,
            city2_container,
        ) = driver.find_elements(By.CSS_SELECTOR, ".select2-selection--single")

        # selecting a country really does it
        country_container.click()
        WebDriverWait(driver, 60).until(
            expected_conditions.presence_of_element_located(
                (By.CSS_SELECTOR, ".select2-results li:nth-child(2)")
            )
        )
        country_option = driver.find_element(
            By.CSS_SELECTOR, ".select2-results li:nth-child(2)"
        )
        country_name = country_option.text
        country_option.click()
        assert country_name == country_container.text

        # selecting a city2
        city2_container.click()
        WebDriverWait(driver, 60).until(
            expected_conditions.presence_of_element_located(
                (By.CSS_SELECTOR, ".select2-results li")
            )
        )
        city2_option = driver.find_element(
            By.CSS_SELECTOR, ".select2-results li:nth-child(2)"
        )
        city2_name = city2_option.text
        city2_option.click()
        assert city2_name == city2_container.text

        # change a country
        country_container.click()
        WebDriverWait(driver, 60).until(
            expected_conditions.presence_of_element_located(
                (By.CSS_SELECTOR, ".select2-results li:nth-child(3)")
            )
        )
        country_option = driver.find_element(
            By.CSS_SELECTOR, ".select2-results li:nth-child(3)"
        )
        country_name = country_option.text
        country_option.click()
        assert country_name == country_container.text

        # check the value in city2
        city2_container.click()
        WebDriverWait(driver, 60).until(
            expected_conditions.presence_of_element_located(
                (By.CSS_SELECTOR, ".select2-results li")
            )
        )
        assert city2_container.text == ""


@pytest.fixture(
    name="widget",
    params=[
        (Select2Widget, {}),
        (HeavySelect2Widget, {"data_view": "heavy_data_1"}),
        (HeavySelect2MultipleWidget, {"data_view": "heavy_data_1"}),
        (ModelSelect2Widget, {}),
        (ModelSelect2TagWidget, {}),
    ],
    ids=lambda p: p[0],
)
def widget_fixture(request):
    widget_class, widget_kwargs = request.param
    return widget_class(**widget_kwargs)


@pytest.mark.parametrize(
    "locale,expected",
    [
        ("fr-FR", "fr"),
        # Some locales with a country code are natively supported by select2's i18n
        ("pt-BR", "pt-BR"),
        ("sr-Cyrl", "sr-Cyrl"),
    ],
    ids=repr,
)
def test_i18n_name_property_with_country_code_in_locale(widget, locale, expected):
    """Test we fall back to the language code if the locale contain an unsupported country code."""
    with translation.override(locale):
        assert widget.i18n_name == expected


def test_i18n_media_js_with_country_code_in_locale(widget):
    translation.activate("fr-FR")
    assert tuple(widget.media._js) == (
        "admin/js/vendor/select2/select2.full.min.js",
        "admin/js/vendor/select2/i18n/fr.js",
        "django_select2/django_select2.js",
    )
