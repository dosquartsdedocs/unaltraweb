# frozen_string_literal: true

require "json"

module Unaltraweb
  module ManualReleaseMetadata
    SELECTOR = /\A(?:latest|v[0-9]{4}\.(?:0[1-9]|1[0-2])(?:\.[1-9][0-9]*)?)\z/
    module_function

    def metadata(site)
      unaltraweb = site.config["unaltraweb"] || {}
      manual = unaltraweb["manual"] || {}
      configured = (manual["release"] || {})["selector"]
      selector = ENV.fetch("UNALTRAWEB_MANUAL_RELEASE_SELECTOR", configured || "latest").to_s.strip
      unless SELECTOR.match?(selector)
        raise Jekyll::Errors::FatalException,
              "UNALTRAWEB_MANUAL_RELEASE_SELECTOR must be latest, vYYYY.MM, or vYYYY.MM.N"
      end

      {
        "channel" => selector == "latest" ? "latest" : "stable",
        "schema_version" => 1,
        "selector" => selector,
      }
    end

    class Generator < Jekyll::Generator
      safe true
      priority :highest

      def generate(site)
        unaltraweb = site.config["unaltraweb"] || {}
        return unless unaltraweb["site_profile"].to_s == "unaltremanual"

        manual = unaltraweb["manual"] ||= {}
        release = ManualReleaseMetadata.metadata(site)
        manual["release"] = release

        page = Jekyll::PageWithoutAFile.new(site, site.source, "", "manual-release.json")
        page.content = JSON.pretty_generate(release) + "\n"
        page.data["layout"] = nil
        page.data["sitemap"] = false
        site.pages << page
      end
    end
  end
end
