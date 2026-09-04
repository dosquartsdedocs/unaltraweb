# frozen_string_literal: true

require "jekyll"
require "minitest/autorun"
require "ostruct"
require "tmpdir"
require "fileutils"

require_relative "../../_plugins/bibliography_profiles"
require_relative "../../_plugins/hide-custom-bibtex"

class BibliographyProfilesTest < Minitest::Test
  def test_manual_profile_uses_alphabetical_ungrouped_bibliographies
    site = site_for("unaltremanual", "query" => "@*[manual=true]")

    Unaltraweb::BibliographyProfiles.configure(site)

    assert_equal %w[name year title], site.config.dig("scholar", "sort_by")
    assert_equal %w[ascending ascending ascending], site.config.dig("scholar", "order")
    assert_equal "none", site.config.dig("scholar", "group_by")
    assert_equal "manual.bib", site.config.dig("scholar", "bibliography")
    assert_equal "@*", site.config.dig("scholar", "query")
    assert_equal "_bibliography", site.config.dig("scholar", "source")
  end

  def test_personal_and_project_profiles_use_reverse_chronological_order
    %w[unaltreselfie unaltreprojecte].each do |profile|
      site = site_for(profile)

      Unaltraweb::BibliographyProfiles.configure(site)

      assert_equal %w[year month name title], site.config.dig("scholar", "sort_by")
      assert_equal %w[descending descending ascending ascending], site.config.dig("scholar", "order")
      assert_equal "year", site.config.dig("scholar", "group_by")
      assert_equal "descending", site.config.dig("scholar", "group_order")
    end
  end

  def test_manual_profile_honors_its_configured_bibliography_file
    site = OpenStruct.new(
      config: {
        "unaltraweb" => {"site_profile" => "unaltremanual", "manual" => {"bibliography_file" => "course.bib"}},
        "scholar" => {}
      }
    )

    Unaltraweb::BibliographyProfiles.configure(site)

    assert_equal "course.bib", site.config.dig("scholar", "bibliography")
  end

  def test_manual_profile_rejects_a_bibliography_path
    site = OpenStruct.new(
      config: {
        "unaltraweb" => {"site_profile" => "unaltremanual", "manual" => {"bibliography_file" => "../outside.bib"}},
        "scholar" => {}
      }
    )

    error = assert_raises(Jekyll::Errors::FatalException) do
      Unaltraweb::BibliographyProfiles.configure(site)
    end

    assert_includes error.message, "must be a .bib filename"
  end

  def test_manual_profile_rejects_a_bibliography_symlink_outside_the_site
    Dir.mktmpdir do |directory|
      source = File.join(directory, "site")
      bibliography = File.join(source, "_bibliography")
      Dir.mkdir(source)
      Dir.mkdir(bibliography)
      outside = File.join(directory, "outside.bib")
      File.write(outside, "@book{outside, title={Outside}}\n")
      File.symlink(outside, File.join(bibliography, "manual.bib"))
      site = OpenStruct.new(
        source: source,
        config: {"unaltraweb" => {"site_profile" => "unaltremanual"}, "scholar" => {}}
      )

      error = assert_raises(Jekyll::Errors::FatalException) do
        Unaltraweb::BibliographyProfiles.configure(site)
      end

      assert_includes error.message, "must remain under"
    end
  end

  def test_manual_render_folds_unicode_and_latex_accents_and_keeps_numeric_citations_linked_to_their_labels
    Dir.mktmpdir do |directory|
      source = File.join(directory, "site")
      destination = File.join(directory, "output")
      FileUtils.mkdir_p(File.join(source, "_bibliography"))
      File.write(
        File.join(source, "_bibliography", "manual.bib"),
        <<~BIBLIOGRAPHY
          @book{zulu, author={Zulu, Ada}, title={Zulu title}, year={2026}}
          @book{eclair, author={Éclair, Ada}, title={Eclair title}, year={2026}}
          @book{agency, author={{Agency Alpha}}, title={Agency title}, year={2026}}
          @book{bruns, author={Bruns, Ada}, title={Bruns title}, year={2026}}
          @book{boeckmann, author={B{\"o}ckmann, Ada}, title={Boeckmann title}, year={2026}}
        BIBLIOGRAPHY
      )
      File.write(
        File.join(source, "index.md"),
        <<~MARKDOWN
          ---
          ---
          {% cite zulu %} {% cite eclair %} {% cite agency %} {% cite bruns %} {% cite boeckmann %}

          {% bibliography --cited --group_by none %}
        MARKDOWN
      )
      style = File.expand_path("../manual_pdf/fixtures/bibliography-filter/numeric.csl", __dir__)
      config = Jekyll.configuration(
        "source" => source,
        "destination" => destination,
        "quiet" => true,
        "unaltraweb" => {"site_profile" => "unaltremanual", "manual" => {}},
        "scholar" => {
          "style" => style,
          "source" => File.join(directory, "outside"),
          "bibliography" => "external.bib",
          "bibliography_template" => "{{reference}}",
          "sort_by" => "none",
          "query" => "@*"
        }
      )

      Jekyll::Site.new(config).process
      output = File.read(File.join(destination, "index.html"))

      assert_operator output.index('id="agency"'), :<, output.index('id="eclair"')
      assert_operator output.index('id="boeckmann"'), :<, output.index('id="bruns"')
      assert_operator output.index('id="bruns"'), :<, output.index('id="eclair"')
      assert_operator output.index('id="eclair"'), :<, output.index('id="zulu"')
      assert_match(/href="#zulu"[^>]*>\[1\]<\/a>/, output)
      assert_match(/href="#eclair"[^>]*>\[2\]<\/a>/, output)
      assert_match(/href="#agency"[^>]*>\[3\]<\/a>/, output)
      assert_match(/href="#bruns"[^>]*>\[4\]<\/a>/, output)
      assert_match(/href="#boeckmann"[^>]*>\[5\]<\/a>/, output)
      assert_match(/id="agency"[^>]*>3\. Agency title/, output)
      assert_match(/id="boeckmann"[^>]*>5\. Boeckmann title/, output)
      assert_match(/id="bruns"[^>]*>4\. Bruns title/, output)
      assert_match(/id="eclair"[^>]*>2\. Eclair title/, output)
      assert_match(/id="zulu"[^>]*>1\. Zulu title/, output)
    end
  end

  def test_manual_bibliography_keeps_featured_readings_and_hides_access_from_citation_panels
    Dir.mktmpdir do |directory|
      source = File.join(directory, "site")
      destination = File.join(directory, "output")
      root = File.expand_path("../..", __dir__)
      %w[
        _includes/manual-bibliography.liquid
        _includes/manual-featured-readings.liquid
        _includes/manual-other-readings.liquid
        _includes/reading-biblio-controls.liquid
        _includes/t.liquid
        _layouts/manual-bib.liquid
        _layouts/manual-featured-bib.liquid
      ].each do |relative_path|
        target = File.join(source, relative_path)
        FileUtils.mkdir_p(File.dirname(target))
        FileUtils.cp(File.join(root, relative_path), target)
      end
      FileUtils.mkdir_p(File.join(source, "_bibliography"))
      File.write(
        File.join(source, "_bibliography", "manual.bib"),
        <<~BIBLIOGRAPHY
          @book{selected, author={Selected, Ada}, title={Selected title}, year={2020}, manual={true}, manual_selected={true}}
          @article{other, author={Other, Ada}, title={Other title}, journal={Journal}, year={2021}, manual={true}, manual_selected={false}, doi={10.1234/other}}
        BIBLIOGRAPHY
      )
      File.write(
        File.join(source, "index.md"),
        <<~MARKDOWN
          ---
          lang: en
          ref: manual-bibliography
          ---
          {% include manual-bibliography.liquid %}
        MARKDOWN
      )
      config = Jekyll.configuration(
        "source" => source,
        "destination" => destination,
        "quiet" => true,
        "default_lang" => "en",
        "lang" => "en",
        "filtered_bibtex_keywords" => [],
        "unaltraweb" => {"site_profile" => "unaltremanual", "manual" => {}},
        "scholar" => {"style" => "apa", "bibliography_template" => "manual-bib"}
      )

      Jekyll::Site.new(config).process
      output = File.read(File.join(destination, "index.html"))
      visible_reference = output[/<div class="manual-reference-text">(.*?)<\/div>/m, 1]
      citation_panel = output[/id="biblio-other-cite-copy"[^>]*>(.*?)<\/div>/m, 1]

      assert_includes output, "Selected readings"
      assert_includes output, "More readings"
      assert_operator output.index("manual-featured-bibliography"), :<, output.index("manual-more-bibliography")
      assert_includes output, "manual-featured-reference"
      assert_includes output, "Other title"
      refute_includes visible_reference, "doi.org"
      refute_includes citation_panel, "doi.org"
      refute_includes output, "reading-citation-doi"
      assert_includes output, 'href="https://doi.org/10.1234/other"'
    end
  end

  def test_unrelated_profile_keeps_existing_scholar_configuration
    site = site_for("unaltredocs", "sort_by" => "title")

    Unaltraweb::BibliographyProfiles.configure(site)

    assert_equal({"sort_by" => "title"}, site.config["scholar"])
  end

  def test_web_reference_hides_trailing_doi_but_keeps_the_citation
    reference = '<span id="example">Example, A. (2026). Title. <i>Journal</i>, 1, 1–9. https://doi.org/10.1234/example</span>'

    result = Unaltraweb::BibliographyProfiles.strip_web_access(reference, "10.1234/example")

    assert_equal '<span id="example">Example, A. (2026). Title. <i>Journal</i>, 1, 1–9.</span>', result
  end

  def test_web_reference_hides_trailing_url_in_plain_text_or_anchor
    plain = "Agency. (2026). Report. https://example.test/report"
    linked = 'Agency. (2026). Report. <a href="https://example.test/report">https://example.test/report</a>'

    assert_equal "Agency. (2026). Report.", Unaltraweb::BibliographyProfiles.strip_web_access(plain, nil, "https://example.test/report")
    assert_equal "Agency. (2026). Report.", Unaltraweb::BibliographyProfiles.strip_web_access(linked, nil, "https://example.test/report")
  end

  def test_web_reference_can_hide_standard_and_manual_urls
    reference = "Agency. (2026). Report. https://example.test/standard https://example.test/manual"

    result = Unaltraweb::BibliographyProfiles.strip_web_access(
      reference,
      nil,
      "https://example.test/standard",
      "https://example.test/manual"
    )

    assert_equal "Agency. (2026). Report.", result
  end

  def test_reference_ids_are_removed_from_rendered_citeproc_html
    reference = '<span id="example">Example <a id="nested" href="#">link</a></span>'

    assert_equal '<span>Example <a href="#">link</a></span>', Unaltraweb::BibliographyProfiles.strip_reference_ids(reference)
  end

  def test_liquid_opening_markers_are_encoded_for_bibtex_panels
    bibtex = "author = {{Example Agency}}, note = {% raw %}"

    result = Unaltraweb::BibliographyProfiles.escape_liquid_markers(bibtex)

    assert_equal "author = <span>{</span>{Example Agency}}, note = <span>{</span>% raw %}", result
    refute_match(/{{.*?}}|{%.*?%}/, result)
  end

  private

  def site_for(profile, scholar = {})
    OpenStruct.new(config: {"unaltraweb" => {"site_profile" => profile}, "scholar" => scholar})
  end
end
