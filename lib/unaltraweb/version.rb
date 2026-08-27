# frozen_string_literal: true

require "json"

module Unaltraweb
  contract_path = File.expand_path("../../src/unaltraweb_mcp/component-contract.json", __dir__)
  VERSION = JSON.parse(File.read(contract_path)).fetch("release").fetch("version") unless const_defined?(:VERSION, false)
end
