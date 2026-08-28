# frozen_string_literal: true

require "jekyll"
require "minitest/autorun"
require "ostruct"
require "tmpdir"
require "fileutils"

require_relative "../../_plugins/bibliography_profiles"

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

  def test_manual_render_folds_accents_and_keeps_numeric_citations_linked_to_their_labels
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
        BIBLIOGRAPHY
      )
      File.write(
        File.join(source, "index.md"),
        <<~MARKDOWN
          ---
          ---
          {% cite zulu %} {% cite eclair %} {% cite agency %}

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
      assert_operator output.index('id="eclair"'), :<, output.index('id="zulu"')
      assert_match(/href="#zulu"[^>]*>\[1\]<\/a>/, output)
      assert_match(/href="#eclair"[^>]*>\[2\]<\/a>/, output)
      assert_match(/href="#agency"[^>]*>\[3\]<\/a>/, output)
      assert_match(/id="agency"[^>]*>3\. Agency title/, output)
      assert_match(/id="eclair"[^>]*>2\. Eclair title/, output)
      assert_match(/id="zulu"[^>]*>1\. Zulu title/, output)
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
