# frozen_string_literal: true

module Unaltraweb
  module ProfilePages
    module_function

    def active_profile(site)
      unaltraweb_config = site.config["unaltraweb"] || {}
      (unaltraweb_config["site_profile"] || unaltraweb_config["site_type"] || "project").to_s
    end

    def keep_item?(item, profile)
      profiles = item.data["profiles"] || item.data["site_profiles"]
      return true if profiles.nil? || profiles.empty?

      Array(profiles).map(&:to_s).include?(profile)
    end
  end
end

Jekyll::Hooks.register :site, :post_read do |site|
  active_profile = Unaltraweb::ProfilePages.active_profile(site)

  site.pages.select! { |page| Unaltraweb::ProfilePages.keep_item?(page, active_profile) }
  site.collections.each_value do |collection|
    collection.docs.select! { |doc| Unaltraweb::ProfilePages.keep_item?(doc, active_profile) }
  end
end
