# frozen_string_literal: true

require "time"

module Unaltraweb
  module ReproducibleBuildTime
    EPOCH = /\A[0-9]+\z/
    module_function

    def build_time
      raw = ENV["SOURCE_DATE_EPOCH"]
      return if raw.nil?

      unless EPOCH.match?(raw)
        raise Jekyll::Errors::FatalException,
              "SOURCE_DATE_EPOCH must be a non-negative base-10 integer"
      end

      time = Time.at(Integer(raw, 10)).utc
      time
    rescue ArgumentError, RangeError => error
      raise Jekyll::Errors::FatalException,
            "Invalid SOURCE_DATE_EPOCH: #{error.message}"
    end

    def apply(site)
      time = build_time
      return unless time

      site.config["time"] = time.iso8601
      site.time = time
    end

    def normalize_static_files(site)
      time = build_time
      return unless time

      site.static_files.each do |file|
        file.instance_variable_set(:@modified_time, time)
      end
    end
  end
end

Jekyll::Hooks.register :site, :after_init do |site|
  Unaltraweb::ReproducibleBuildTime.apply(site)
end

Jekyll::Hooks.register :site, :after_reset do |site|
  Unaltraweb::ReproducibleBuildTime.apply(site)
end

Jekyll::Hooks.register :site, :post_read do |site|
  Unaltraweb::ReproducibleBuildTime.normalize_static_files(site)
end
