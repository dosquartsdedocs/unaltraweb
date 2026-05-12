# frozen_string_literal: true

require_relative "unaltraweb/version"

%w[
  details
  external-posts
  file-exists
  google-scholar-citations
  hide-custom-bibtex
  inspirehep-citations
  remove-accents
].each do |plugin|
  require File.expand_path("../_plugins/#{plugin}", __dir__)
end
