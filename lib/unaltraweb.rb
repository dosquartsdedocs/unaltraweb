# frozen_string_literal: true

require_relative "unaltraweb/version"

%w[
  details
  external-posts
  file-exists
  google-scholar-citations
  hide-custom-bibtex
  inspirehep-citations
  profile-pages
  remove-accents
  search-data
  theme-cache-bust
].each do |plugin|
  require File.expand_path("../_plugins/#{plugin}", __dir__)
end
