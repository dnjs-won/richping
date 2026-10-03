---
updatedAt: 2026-05-27T17:58:03.000Z
agentTools:
  siteIndex: https://docs.alpaca.markets/llms.txt
  projectIndex: https://docs.alpaca.markets/us/llms.txt
---

# Corporate actions

This endpoint provides data about the corporate actions for each given symbol over a specified time period.

By default (`data_quality=complete`), corporate actions that are still incomplete (for example, missing required fields such as ex-date or CUSIP/ISIN) and have not yet been processed are excluded from the response. Pass `data_quality=all` to also receive those early, incomplete records. Already-processed corporate actions are always returned when `data_quality=complete`, even if they would otherwise be considered incomplete.

> ⚠️ Warning
>
> Currently Alpaca has no guarantees on the creation time of corporate actions. There may be delays in receiving corporate actions from our data providers, and there may be delays in processing and making them available via this API. As a result, corporate actions may not be available immediately after they are announced.


# OpenAPI definition

```json
{
  "components": {
    "headers": {
      "ratelimit_limit": {
        "description": "Request limit per minute.",
        "example": 100,
        "schema": {
          "type": "integer"
        }
      },
      "ratelimit_remaining": {
        "description": "Request limit per minute remaining.",
        "example": 90,
        "schema": {
          "type": "integer"
        }
      },
      "ratelimit_reset": {
        "description": "The UNIX epoch when the remaining quota changes.",
        "example": 1674044551,
        "schema": {
          "type": "integer"
        }
      }
    },
    "parameters": {
      "cas_cusips": {
        "description": "A comma-separated list of CUSIPs.",
        "example": "037833100,88160R101",
        "in": "query",
        "name": "cusips",
        "schema": {
          "type": "string"
        }
      },
      "cas_data_quality": {
        "description": "Controls which corporate actions are returned based on data quality.\n",
        "in": "query",
        "name": "data_quality",
        "schema": {
          "$ref": "#/components/schemas/data_quality"
        }
      },
      "cas_end": {
        "description": "The inclusive end of the interval. The corporate actions are sorted by their `process_date`. Format: YYYY-MM-DD. Default: current day.\n",
        "examples": {
          "date": {
            "summary": "Date",
            "value": "2024-08-25"
          }
        },
        "in": "query",
        "name": "end",
        "schema": {
          "format": "date",
          "type": "string"
        }
      },
      "cas_ids": {
        "description": "A comma-separated list of corporate action IDs. This parameter is mutually exclusive with all other filters (symbols, types, start, end, region, data_quality).\n",
        "example": "1dbc7685-9517-4a77-a236-8527d49cefdc,f8489167-4e4b-431d-a0be-6017ae1cf08a",
        "in": "query",
        "name": "ids",
        "schema": {
          "type": "string"
        }
      },
      "cas_limit": {
        "description": "Maximum number of corporate actions to return in a response.\nThe limit applies to the total number of data points, not the count per symbol!\nUse `next_page_token` to fetch the next set of corporate actions.\n",
        "in": "query",
        "name": "limit",
        "schema": {
          "default": 100,
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        }
      },
      "cas_region": {
        "description": "The region to filter corporate actions by.",
        "in": "query",
        "name": "region",
        "schema": {
          "$ref": "#/components/schemas/region"
        }
      },
      "cas_start": {
        "description": "The inclusive start of the interval. The corporate actions are sorted by their `process_date`. Format: YYYY-MM-DD. Default: current day.\n",
        "examples": {
          "date": {
            "value": "2024-08-14"
          }
        },
        "in": "query",
        "name": "start",
        "schema": {
          "format": "date",
          "type": "string"
        }
      },
      "cas_symbols": {
        "description": "A comma-separated list of symbols.",
        "example": "AAPL,TSLA",
        "in": "query",
        "name": "symbols",
        "schema": {
          "type": "string"
        }
      },
      "cas_types": {
        "description": "A comma-separated list of types. If not provided, search all types.\n\nThe following types are supported:\n  - reverse_split\n  - forward_split\n  - unit_split\n  - cash_dividend\n  - stock_dividend\n  - spin_off\n  - cash_merger\n  - stock_merger\n  - stock_and_cash_merger\n  - redemption\n  - name_change\n  - worthless_removal\n  - rights_distribution\n  - partial_call\n  - reorganization\n  - capital_gains_distribution\n",
        "example": "forward_split,reverse_split",
        "in": "query",
        "name": "types",
        "schema": {
          "type": "string"
        }
      },
      "page_token": {
        "description": "The pagination token from which to continue. The value to pass here is returned in specific requests when more data is available, usually because of a response result limit.\n",
        "in": "query",
        "name": "page_token",
        "schema": {
          "type": "string"
        }
      },
      "sort": {
        "description": "Sort data in ascending or descending order.",
        "in": "query",
        "name": "sort",
        "schema": {
          "allOf": [
            {
              "type": "string"
            },
            {
              "$ref": "#/components/schemas/sort"
            }
          ]
        }
      }
    },
    "responses": {
      "400": {
        "description": "One of the request parameters is invalid. See the returned message for details.\n",
        "headers": {
          "X-RateLimit-Limit": {
            "$ref": "#/components/headers/ratelimit_limit"
          },
          "X-RateLimit-Remaining": {
            "$ref": "#/components/headers/ratelimit_remaining"
          },
          "X-RateLimit-Reset": {
            "$ref": "#/components/headers/ratelimit_reset"
          }
        }
      },
      "401": {
        "description": "Authentication headers are missing or invalid. Make sure you authenticate your request with a valid API key.\n"
      },
      "403": {
        "description": "The requested resource is forbidden.\n"
      },
      "429": {
        "description": "Too many requests. You hit the rate limit. Use the X-RateLimit-... response headers to make sure you're under the rate limit.\n",
        "headers": {
          "X-RateLimit-Limit": {
            "$ref": "#/components/headers/ratelimit_limit"
          },
          "X-RateLimit-Remaining": {
            "$ref": "#/components/headers/ratelimit_remaining"
          },
          "X-RateLimit-Reset": {
            "$ref": "#/components/headers/ratelimit_reset"
          }
        }
      },
      "500": {
        "description": "Internal server error. We recommend retrying these later. If the issue persists, please contact us on [Slack](https://alpaca.markets/slack) or on the [Community Forum](https://forum.alpaca.markets/).\n"
      }
    },
    "schemas": {
      "ca_id": {
        "description": "The internal Alpaca identifier of the corporate action.",
        "format": "uuid",
        "type": "string"
      },
      "capital_gains_distribution": {
        "description": "Capital gains distribution paid by a fund. A single event may carry a long-term\nleg (`long_term_rate`), a short-term leg (`short_term_rate`), or both when\ncombined. At least one of the two rates is always present.\n",
        "examples": [
          {
            "currency": "USD",
            "cusip": "36261K509",
            "ex_date": "2025-12-26",
            "id": "98c905a1-08c7-450c-8669-b8e7aee8b44d",
            "isin": "US36261K5090",
            "long_term_rate": 0.45855,
            "payable_date": "2026-01-09",
            "process_date": "2026-01-08",
            "record_date": "2025-12-29",
            "short_term_rate": 0.11019,
            "symbol": "GCAD"
          }
        ],
        "properties": {
          "currency": {
            "$ref": "#/components/schemas/currency"
          },
          "cusip": {
            "type": "string"
          },
          "ex_date": {
            "$ref": "#/components/schemas/ex_date"
          },
          "id": {
            "$ref": "#/components/schemas/ca_id"
          },
          "isin": {
            "$ref": "#/components/schemas/isin"
          },
          "long_term_rate": {
            "description": "Long-term capital-gain payment per share.",
            "format": "double",
            "type": "number"
          },
          "payable_date": {
            "$ref": "#/components/schemas/payable_date"
          },
          "process_date": {
            "$ref": "#/components/schemas/process_date"
          },
          "record_date": {
            "$ref": "#/components/schemas/record_date"
          },
          "short_term_rate": {
            "description": "Short-term capital-gain payment per share.",
            "format": "double",
            "type": "number"
          },
          "symbol": {
            "type": "string"
          }
        },
        "required": [
          "id",
          "symbol",
          "cusip",
          "process_date",
          "ex_date"
        ],
        "type": "object"
      },
      "cash_dividend": {
        "description": "Cash dividend.",
        "examples": [
          {
            "cusip": "319829107",
            "ex_date": "2023-05-04",
            "foreign": false,
            "id": "11cfd108-292e-4cc6-bfbf-5999cdbc4029",
            "payable_date": "2023-05-19",
            "process_date": "2023-05-19",
            "rate": 0.125,
            "record_date": "2023-05-05",
            "special": false,
            "symbol": "FCF"
          }
        ],
        "properties": {
          "currency": {
            "$ref": "#/components/schemas/currency"
          },
          "cusip": {
            "type": "string"
          },
          "due_bill_off_date": {
            "format": "date",
            "type": "string"
          },
          "due_bill_on_date": {
            "format": "date",
            "type": "string"
          },
          "ex_date": {
            "$ref": "#/components/schemas/ex_date"
          },
          "foreign": {
            "type": "boolean"
          },
          "id": {
            "$ref": "#/components/schemas/ca_id"
          },
          "isin": {
            "$ref": "#/components/schemas/isin"
          },
          "payable_date": {
            "$ref": "#/components/schemas/payable_date"
          },
          "process_date": {
            "$ref": "#/components/schemas/process_date"
          },
          "rate": {
            "format": "double",
            "type": "number"
          },
          "record_date": {
            "$ref": "#/components/schemas/record_date"
          },
          "special": {
            "type": "boolean"
          },
          "sub_type": {
            "description": "Sub-type of the cash dividend.",
            "enum": [
              "interest",
              "return_of_capital"
            ],
            "type": "string"
          },
          "symbol": {
            "type": "string"
          }
        },
        "required": [
          "id",
          "symbol",
          "cusip",
          "rate",
          "special",
          "foreign",
          "process_date",
          "ex_date"
        ],
        "type": "object"
      },
      "cash_merger": {
        "description": "Cash merger.",
        "examples": [
          {
            "acquiree_cusip": "Y2687W108",
            "acquiree_symbol": "GLOP",
            "effective_date": "2023-07-17",
            "id": "3772bbd7-4ad5-44d4-9cc0-f69156a2f8f5",
            "payable_date": "2023-07-17",
            "process_date": "2023-07-17",
            "rate": 5.37
          }
        ],
        "properties": {
          "acquiree_cusip": {
            "type": "string"
          },
          "acquiree_isin": {
            "$ref": "#/components/schemas/isin"
          },
          "acquiree_symbol": {
            "type": "string"
          },
          "acquirer_cusip": {
            "type": "string"
          },
          "acquirer_isin": {
            "$ref": "#/components/schemas/isin"
          },
          "acquirer_symbol": {
            "type": "string"
          },
          "currency": {
            "$ref": "#/components/schemas/currency"
          },
          "effective_date": {
            "$ref": "#/components/schemas/effective_date"
          },
          "id": {
            "$ref": "#/components/schemas/ca_id"
          },
          "payable_date": {
            "$ref": "#/components/schemas/payable_date"
          },
          "process_date": {
            "$ref": "#/components/schemas/process_date"
          },
          "rate": {
            "format": "double",
            "type": "number"
          }
        },
        "required": [
          "id",
          "acquiree_symbol",
          "acquiree_cusip",
          "rate",
          "process_date",
          "effective_date"
        ],
        "type": "object"
      },
      "corporate_actions": {
        "properties": {
          "capital_gains_distributions": {
            "items": {
              "$ref": "#/components/schemas/capital_gains_distribution"
            },
            "type": "array"
          },
          "cash_dividends": {
            "items": {
              "$ref": "#/components/schemas/cash_dividend"
            },
            "type": "array"
          },
          "cash_mergers": {
            "items": {
              "$ref": "#/components/schemas/cash_merger"
            },
            "type": "array"
          },
          "forward_splits": {
            "items": {
              "$ref": "#/components/schemas/forward_split"
            },
            "type": "array"
          },
          "name_changes": {
            "items": {
              "$ref": "#/components/schemas/name_change"
            },
            "type": "array"
          },
          "partial_calls": {
            "items": {
              "$ref": "#/components/schemas/partial_call"
            },
            "type": "array"
          },
          "redemptions": {
            "items": {
              "$ref": "#/components/schemas/redemption"
            },
            "type": "array"
          },
          "reorganizations": {
            "items": {
              "$ref": "#/components/schemas/reorganization"
            },
            "type": "array"
          },
          "reverse_splits": {
            "items": {
              "$ref": "#/components/schemas/reverse_split"
            },
            "type": "array"
          },
          "rights_distributions": {
            "items": {
              "$ref": "#/components/schemas/rights_distribution"
            },
            "type": "array"
          },
          "spin_offs": {
            "items": {
              "$ref": "#/components/schemas/spin_off"
            },
            "type": "array"
          },
          "stock_and_cash_mergers": {
            "items": {
              "$ref": "#/components/schemas/stock_and_cash_merger"
            },
            "type": "array"
          },
          "stock_dividends": {
            "items": {
              "$ref": "#/components/schemas/stock_dividend"
            },
            "type": "array"
          },
          "stock_mergers": {
            "items": {
              "$ref": "#/components/schemas/stock_merger"
            },
            "type": "array"
          },
          "unit_splits": {
            "items": {
              "$ref": "#/components/schemas/unit_split"
            },
            "type": "array"
          },
          "worthless_removals": {
            "items": {
              "$ref": "#/components/schemas/worthless_removal"
            },
            "type": "array"
          }
        },
        "type": "object"
      },
      "corporate_actions_resp": {
        "properties": {
          "corporate_actions": {
            "$ref": "#/components/schemas/corporate_actions"
          },
          "next_page_token": {
            "$ref": "#/components/schemas/next_page_token"
          }
        },
        "required": [
          "corporate_actions",
          "next_page_token"
        ],
        "type": "object"
      },
      "currency": {
        "description": "The ISO 4217 currency code associated with the corporate action.\nEmpty value can mean USD, non-applicable (e.g. for name changes) or unknown\n(can change later to a valid currency).\n",
        "type": "string"
      },
      "data_quality": {
        "default": "complete",
        "description": "Controls which corporate actions are returned based on data quality.\n\n- `complete` (default): exclude corporate actions that are still missing required\n  fields (for example, ex-date or CUSIP/ISIN) and have not yet been processed.\n  Already-processed corporate actions are always included, even if they would\n  otherwise be considered incomplete.\n- `all`: return matching corporate actions regardless of field completeness.\n",
        "enum": [
          "complete",
          "all"
        ],
        "type": "string"
      },
      "due_bill_redemption_date": {
        "description": "The date when due bill obligations are redeemed.",
        "format": "date",
        "type": "string"
      },
      "effective_date": {
        "description": "The effective date marks the cutoff point for shareholders to be credited.",
        "format": "date",
        "type": "string"
      },
      "ex_date": {
        "description": "The ex-date marks the cutoff point for shareholders to be credited.",
        "format": "date",
        "type": "string"
      },
      "expiration_date": {
        "format": "date",
        "type": "string"
      },
      "forward_split": {
        "description": "Forward split.",
        "examples": [
          {
            "cusip": "816851109",
            "due_bill_redemption_date": "2023-08-23",
            "ex_date": "2023-08-22",
            "id": "189bd849-ab9f-4b4d-aaaa-a6d415fd976d",
            "new_rate": 2,
            "old_rate": 1,
            "payable_date": "2023-08-21",
            "process_date": "2023-08-22",
            "record_date": "2023-08-14",
            "symbol": "SRE"
          }
        ],
        "properties": {
          "currency": {
            "$ref": "#/components/schemas/currency"
          },
          "cusip": {
            "type": "string"
          },
          "due_bill_redemption_date": {
            "$ref": "#/components/schemas/due_bill_redemption_date"
          },
          "ex_date": {
            "$ref": "#/components/schemas/ex_date"
          },
          "id": {
            "$ref": "#/components/schemas/ca_id"
          },
          "isin": {
            "$ref": "#/components/schemas/isin"
          },
          "new_rate": {
            "format": "double",
            "type": "number"
          },
          "old_rate": {
            "format": "double",
            "type": "number"
          },
          "payable_date": {
            "$ref": "#/components/schemas/payable_date"
          },
          "process_date": {
            "$ref": "#/components/schemas/process_date"
          },
          "record_date": {
            "$ref": "#/components/schemas/record_date"
          },
          "symbol": {
            "type": "string"
          }
        },
        "required": [
          "id",
          "symbol",
          "cusip",
          "new_rate",
          "old_rate",
          "process_date",
          "ex_date"
        ],
        "type": "object"
      },
      "isin": {
        "description": "International Securities Identification Number (ISIN) as defined by ISO 6166.\nMay be empty for US corporate actions.\n",
        "type": "string"
      },
      "name_change": {
        "description": "Name change.",
        "examples": [
          {
            "id": "5a774c35-edec-4532-a812-a56d0bbb623a",
            "new_cusip": "Y9390M103",
            "new_symbol": "VFS",
            "old_cusip": "G11537100",
            "old_symbol": "BSAQ",
            "process_date": "2023-08-15"
          }
        ],
        "properties": {
          "currency": {
            "$ref": "#/components/schemas/currency"
          },
          "id": {
            "$ref": "#/components/schemas/ca_id"
          },
          "new_cusip": {
            "type": "string"
          },
          "new_isin": {
            "$ref": "#/components/schemas/isin"
          },
          "new_symbol": {
            "type": "string"
          },
          "old_cusip": {
            "type": "string"
          },
          "old_isin": {
            "$ref": "#/components/schemas/isin"
          },
          "old_symbol": {
            "type": "string"
          },
          "process_date": {
            "$ref": "#/components/schemas/process_date"
          }
        },
        "required": [
          "id",
          "old_symbol",
          "old_cusip",
          "new_symbol",
          "new_cusip",
          "process_date"
        ],
        "type": "object"
      },
      "next_page_token": {
        "description": "Pagination token for the next page.",
        "type": [
          "string",
          "null"
        ]
      },
      "partial_call": {
        "description": "Partial call.",
        "properties": {
          "currency": {
            "$ref": "#/components/schemas/currency"
          },
          "cusip": {
            "type": "string"
          },
          "dividend_rate": {
            "format": "double",
            "type": "number"
          },
          "id": {
            "$ref": "#/components/schemas/ca_id"
          },
          "isin": {
            "$ref": "#/components/schemas/isin"
          },
          "lottery_date": {
            "format": "date",
            "type": "string"
          },
          "lottery_type": {
            "description": "The type of lottery for the partial call.",
            "enum": [
              "original",
              "supplemental"
            ],
            "type": "string"
          },
          "payable_date": {
            "$ref": "#/components/schemas/payable_date"
          },
          "price": {
            "format": "double",
            "type": "number"
          },
          "process_date": {
            "$ref": "#/components/schemas/process_date"
          },
          "record_date": {
            "$ref": "#/components/schemas/record_date"
          },
          "results_publication_date": {
            "format": "date",
            "type": "string"
          },
          "symbol": {
            "type": "string"
          }
        },
        "required": [
          "id",
          "symbol",
          "process_date"
        ],
        "type": "object"
      },
      "payable_date": {
        "description": "The date when the corporate action benefit is paid or distributed.",
        "format": "date",
        "type": "string"
      },
      "process_date": {
        "description": "The date when the corporate action is processed by Alpaca.",
        "format": "date",
        "type": "string"
      },
      "record_date": {
        "description": "The date shareholders must own shares to receive the benefit.",
        "format": "date",
        "type": "string"
      },
      "redemption": {
        "description": "Redemption.",
        "examples": [
          {
            "cusip": "687305102",
            "id": "395da031-0e57-4918-a6fb-64a7c713aca4",
            "payable_date": "2023-06-13",
            "process_date": "2023-06-13",
            "rate": 0.141134,
            "symbol": "ORPHY"
          }
        ],
        "properties": {
          "currency": {
            "$ref": "#/components/schemas/currency"
          },
          "cusip": {
            "type": "string"
          },
          "id": {
            "$ref": "#/components/schemas/ca_id"
          },
          "isin": {
            "$ref": "#/components/schemas/isin"
          },
          "payable_date": {
            "$ref": "#/components/schemas/payable_date"
          },
          "process_date": {
            "$ref": "#/components/schemas/process_date"
          },
          "rate": {
            "format": "double",
            "type": "number"
          },
          "symbol": {
            "type": "string"
          }
        },
        "required": [
          "id",
          "symbol",
          "cusip",
          "rate",
          "process_date"
        ],
        "type": "object"
      },
      "region": {
        "default": "us",
        "description": "The region to filter corporate actions by.\n\n- `us`: only US corporate actions\n- `non_us`: only non-US corporate actions\n- `all`: both US and non-US corporate actions\n",
        "enum": [
          "us",
          "non_us",
          "all"
        ],
        "type": "string"
      },
      "reorganization": {
        "description": "Reorganization (cash and/or multiple stock allocations).",
        "properties": {
          "cash_rate": {
            "format": "double",
            "type": "number"
          },
          "currency": {
            "$ref": "#/components/schemas/currency"
          },
          "cusip": {
            "type": "string"
          },
          "effective_date": {
            "$ref": "#/components/schemas/effective_date"
          },
          "id": {
            "$ref": "#/components/schemas/ca_id"
          },
          "isin": {
            "type": "string"
          },
          "payable_date": {
            "$ref": "#/components/schemas/payable_date"
          },
          "process_date": {
            "$ref": "#/components/schemas/process_date"
          },
          "stock_movements": {
            "items": {
              "$ref": "#/components/schemas/reorganization_stock_movement"
            },
            "type": "array"
          },
          "symbol": {
            "type": "string"
          }
        },
        "required": [
          "id",
          "symbol",
          "cusip",
          "process_date",
          "effective_date"
        ],
        "type": "object"
      },
      "reorganization_stock_movement": {
        "description": "A stock allocation leg in a reorganization.",
        "properties": {
          "cusip": {
            "type": "string"
          },
          "isin": {
            "type": "string"
          },
          "new_rate": {
            "format": "double",
            "type": "number"
          },
          "source_rate": {
            "format": "double",
            "type": "number"
          },
          "symbol": {
            "type": "string"
          }
        },
        "required": [
          "symbol",
          "cusip",
          "new_rate",
          "source_rate"
        ],
        "type": "object"
      },
      "reverse_split": {
        "description": "Reverse split.",
        "examples": [
          {
            "ex_date": "2023-08-24",
            "id": "913de862-c02c-46dc-a89c-fc8779a50d30",
            "new_cusip": "60879E200",
            "new_rate": 1,
            "old_cusip": "60879E101",
            "old_rate": 50,
            "process_date": "2023-08-24",
            "record_date": "2023-08-24",
            "symbol": "MNTS"
          }
        ],
        "properties": {
          "currency": {
            "$ref": "#/components/schemas/currency"
          },
          "ex_date": {
            "$ref": "#/components/schemas/ex_date"
          },
          "id": {
            "$ref": "#/components/schemas/ca_id"
          },
          "new_cusip": {
            "type": "string"
          },
          "new_isin": {
            "$ref": "#/components/schemas/isin"
          },
          "new_rate": {
            "format": "double",
            "type": "number"
          },
          "new_symbol": {
            "description": "The post-split ticker. Empty when the reverse split does not change the\nticker (the most common case); only populated when the issuer assigns a\ndifferent symbol after the split.\n",
            "type": "string"
          },
          "old_cusip": {
            "type": "string"
          },
          "old_isin": {
            "$ref": "#/components/schemas/isin"
          },
          "old_rate": {
            "format": "double",
            "type": "number"
          },
          "payable_date": {
            "$ref": "#/components/schemas/payable_date"
          },
          "process_date": {
            "$ref": "#/components/schemas/process_date"
          },
          "record_date": {
            "$ref": "#/components/schemas/record_date"
          },
          "symbol": {
            "type": "string"
          }
        },
        "required": [
          "id",
          "symbol",
          "old_cusip",
          "new_cusip",
          "new_rate",
          "old_rate",
          "process_date",
          "ex_date"
        ],
        "type": "object"
      },
      "rights_distribution": {
        "description": "Rights distribution.",
        "examples": [
          {
            "ex_date": "2024-04-17",
            "expiration_date": "2024-05-14",
            "id": "69794cfd-0adc-4e11-9211-9210a9cf8932",
            "new_cusip": "454089111",
            "new_symbol": "IFN.RTWI",
            "payable_date": "2024-04-19",
            "process_date": "2024-04-19",
            "rate": 1,
            "record_date": "2024-04-18",
            "source_cusip": "454089103",
            "source_symbol": "IFN"
          }
        ],
        "properties": {
          "currency": {
            "$ref": "#/components/schemas/currency"
          },
          "ex_date": {
            "$ref": "#/components/schemas/ex_date"
          },
          "expiration_date": {
            "$ref": "#/components/schemas/expiration_date"
          },
          "id": {
            "$ref": "#/components/schemas/ca_id"
          },
          "new_cusip": {
            "type": "string"
          },
          "new_isin": {
            "$ref": "#/components/schemas/isin"
          },
          "new_symbol": {
            "type": "string"
          },
          "payable_date": {
            "$ref": "#/components/schemas/payable_date"
          },
          "process_date": {
            "$ref": "#/components/schemas/process_date"
          },
          "rate": {
            "format": "double",
            "type": "number"
          },
          "record_date": {
            "$ref": "#/components/schemas/record_date"
          },
          "source_cusip": {
            "type": "string"
          },
          "source_isin": {
            "$ref": "#/components/schemas/isin"
          },
          "source_symbol": {
            "type": "string"
          }
        },
        "required": [
          "id",
          "source_symbol",
          "source_cusip",
          "new_symbol",
          "new_cusip",
          "rate",
          "process_date",
          "ex_date",
          "payable_date"
        ],
        "type": "object"
      },
      "sort": {
        "default": "asc",
        "description": "Sort data in ascending or descending order.",
        "enum": [
          "asc",
          "desc"
        ],
        "type": "string"
      },
      "spin_off": {
        "description": "Spin-off.",
        "examples": [
          {
            "ex_date": "2023-08-15",
            "id": "82e602f6-35bc-4651-a5dd-f6d88ff37c55",
            "new_cusip": "85237B101",
            "new_rate": 1,
            "new_symbol": "SRM",
            "process_date": "2023-08-15",
            "record_date": "2023-08-15",
            "source_cusip": "48208F105",
            "source_rate": 19.35,
            "source_symbol": "JUPW"
          }
        ],
        "properties": {
          "currency": {
            "$ref": "#/components/schemas/currency"
          },
          "due_bill_redemption_date": {
            "$ref": "#/components/schemas/due_bill_redemption_date"
          },
          "ex_date": {
            "$ref": "#/components/schemas/ex_date"
          },
          "id": {
            "$ref": "#/components/schemas/ca_id"
          },
          "new_cusip": {
            "type": "string"
          },
          "new_isin": {
            "$ref": "#/components/schemas/isin"
          },
          "new_rate": {
            "format": "double",
            "type": "number"
          },
          "new_symbol": {
            "type": "string"
          },
          "payable_date": {
            "$ref": "#/components/schemas/payable_date"
          },
          "process_date": {
            "$ref": "#/components/schemas/process_date"
          },
          "record_date": {
            "$ref": "#/components/schemas/record_date"
          },
          "source_cusip": {
            "type": "string"
          },
          "source_isin": {
            "$ref": "#/components/schemas/isin"
          },
          "source_rate": {
            "format": "double",
            "type": "number"
          },
          "source_symbol": {
            "type": "string"
          }
        },
        "required": [
          "id",
          "source_symbol",
          "source_cusip",
          "source_rate",
          "new_symbol",
          "new_cusip",
          "new_rate",
          "process_date",
          "ex_date"
        ],
        "type": "object"
      },
      "stock_and_cash_merger": {
        "description": "Stock and cash merger.",
        "examples": [
          {
            "acquiree_cusip": "561409103",
            "acquiree_rate": 1,
            "acquiree_symbol": "MLVF",
            "acquirer_cusip": "31931U102",
            "acquirer_rate": 0.7733,
            "acquirer_symbol": "FRBA",
            "cash_rate": 7.8,
            "effective_date": "2023-07-18",
            "id": "e5248356-2c06-42cf-aeb9-1595bd616cdb",
            "payable_date": "2023-07-18",
            "process_date": "2023-07-18"
          }
        ],
        "properties": {
          "acquiree_cusip": {
            "type": "string"
          },
          "acquiree_isin": {
            "$ref": "#/components/schemas/isin"
          },
          "acquiree_rate": {
            "format": "double",
            "type": "number"
          },
          "acquiree_symbol": {
            "type": "string"
          },
          "acquirer_cusip": {
            "type": "string"
          },
          "acquirer_isin": {
            "$ref": "#/components/schemas/isin"
          },
          "acquirer_rate": {
            "format": "double",
            "type": "number"
          },
          "acquirer_symbol": {
            "type": "string"
          },
          "cash_rate": {
            "format": "double",
            "type": "number"
          },
          "currency": {
            "$ref": "#/components/schemas/currency"
          },
          "effective_date": {
            "$ref": "#/components/schemas/effective_date"
          },
          "id": {
            "$ref": "#/components/schemas/ca_id"
          },
          "payable_date": {
            "$ref": "#/components/schemas/payable_date"
          },
          "process_date": {
            "$ref": "#/components/schemas/process_date"
          }
        },
        "required": [
          "id",
          "acquirer_symbol",
          "acquirer_cusip",
          "acquirer_rate",
          "acquiree_symbol",
          "acquiree_cusip",
          "acquiree_rate",
          "cash_rate",
          "process_date",
          "effective_date"
        ],
        "type": "object"
      },
      "stock_dividend": {
        "description": "Stock dividend.",
        "examples": [
          {
            "cusip": "605015106",
            "ex_date": "2023-05-19",
            "id": "3ae94c30-2d37-473a-bf29-5f7b4ab6d3ca",
            "payable_date": "2023-05-05",
            "process_date": "2023-05-19",
            "rate": 0.05,
            "record_date": "2023-05-22",
            "symbol": "MSBC"
          }
        ],
        "properties": {
          "currency": {
            "$ref": "#/components/schemas/currency"
          },
          "cusip": {
            "type": "string"
          },
          "ex_date": {
            "$ref": "#/components/schemas/ex_date"
          },
          "id": {
            "$ref": "#/components/schemas/ca_id"
          },
          "isin": {
            "$ref": "#/components/schemas/isin"
          },
          "payable_date": {
            "$ref": "#/components/schemas/payable_date"
          },
          "process_date": {
            "$ref": "#/components/schemas/process_date"
          },
          "rate": {
            "format": "double",
            "type": "number"
          },
          "record_date": {
            "$ref": "#/components/schemas/record_date"
          },
          "symbol": {
            "type": "string"
          }
        },
        "required": [
          "id",
          "symbol",
          "cusip",
          "rate",
          "process_date",
          "ex_date"
        ],
        "type": "object"
      },
      "stock_merger": {
        "description": "Stock merger.",
        "examples": [
          {
            "acquiree_cusip": "53223X107",
            "acquiree_rate": 1,
            "acquiree_symbol": "LSI",
            "acquirer_cusip": "30225T102",
            "acquirer_rate": 0.895,
            "acquirer_symbol": "EXR",
            "effective_date": "2023-07-20",
            "id": "728f8cb2-a00e-4bc7-ad14-d15fe82bbcff",
            "payable_date": "2023-07-20",
            "process_date": "2023-07-20"
          }
        ],
        "properties": {
          "acquiree_cusip": {
            "type": "string"
          },
          "acquiree_isin": {
            "$ref": "#/components/schemas/isin"
          },
          "acquiree_rate": {
            "format": "double",
            "type": "number"
          },
          "acquiree_symbol": {
            "type": "string"
          },
          "acquirer_cusip": {
            "type": "string"
          },
          "acquirer_isin": {
            "$ref": "#/components/schemas/isin"
          },
          "acquirer_rate": {
            "format": "double",
            "type": "number"
          },
          "acquirer_symbol": {
            "type": "string"
          },
          "currency": {
            "$ref": "#/components/schemas/currency"
          },
          "effective_date": {
            "$ref": "#/components/schemas/effective_date"
          },
          "id": {
            "$ref": "#/components/schemas/ca_id"
          },
          "payable_date": {
            "$ref": "#/components/schemas/payable_date"
          },
          "process_date": {
            "$ref": "#/components/schemas/process_date"
          }
        },
        "required": [
          "id",
          "acquirer_symbol",
          "acquirer_cusip",
          "acquirer_rate",
          "acquiree_symbol",
          "acquiree_cusip",
          "acquiree_rate",
          "process_date",
          "effective_date"
        ],
        "type": "object"
      },
      "unit_split": {
        "description": "Unit split.",
        "examples": [
          {
            "alternate_cusip": "G5391L110",
            "alternate_rate": 0.3333,
            "alternate_symbol": "LVROW",
            "effective_date": "2023-03-01",
            "id": "3e68e87e-ae95-4d68-91d1-715d52ef143a",
            "new_cusip": "G5391L102",
            "new_rate": 1,
            "new_symbol": "LVRO",
            "old_cusip": "G8990L119",
            "old_rate": 1,
            "old_symbol": "TPBAU",
            "process_date": "2023-03-01"
          }
        ],
        "properties": {
          "alternate_cusip": {
            "type": "string"
          },
          "alternate_isin": {
            "$ref": "#/components/schemas/isin"
          },
          "alternate_rate": {
            "format": "double",
            "type": "number"
          },
          "alternate_symbol": {
            "type": "string"
          },
          "currency": {
            "$ref": "#/components/schemas/currency"
          },
          "effective_date": {
            "$ref": "#/components/schemas/effective_date"
          },
          "id": {
            "$ref": "#/components/schemas/ca_id"
          },
          "new_cusip": {
            "type": "string"
          },
          "new_isin": {
            "$ref": "#/components/schemas/isin"
          },
          "new_rate": {
            "format": "double",
            "type": "number"
          },
          "new_symbol": {
            "type": "string"
          },
          "old_cusip": {
            "type": "string"
          },
          "old_isin": {
            "$ref": "#/components/schemas/isin"
          },
          "old_rate": {
            "format": "double",
            "type": "number"
          },
          "old_symbol": {
            "type": "string"
          },
          "payable_date": {
            "$ref": "#/components/schemas/payable_date"
          },
          "process_date": {
            "$ref": "#/components/schemas/process_date"
          }
        },
        "required": [
          "id",
          "old_symbol",
          "old_cusip",
          "old_rate",
          "new_symbol",
          "new_cusip",
          "new_rate",
          "alternate_symbol",
          "alternate_cusip",
          "alternate_rate",
          "process_date",
          "effective_date"
        ],
        "type": "object"
      },
      "worthless_removal": {
        "description": "Worthless removal.",
        "examples": [
          {
            "cusip": "078771300",
            "id": "106c2149-ee04-4d2e-a943-98dbb4d21a3c",
            "process_date": "2024-12-19",
            "symbol": "BLPH"
          }
        ],
        "properties": {
          "currency": {
            "$ref": "#/components/schemas/currency"
          },
          "cusip": {
            "type": "string"
          },
          "id": {
            "$ref": "#/components/schemas/ca_id"
          },
          "isin": {
            "$ref": "#/components/schemas/isin"
          },
          "process_date": {
            "$ref": "#/components/schemas/process_date"
          },
          "symbol": {
            "type": "string"
          }
        },
        "required": [
          "id",
          "symbol",
          "cusip",
          "process_date"
        ],
        "type": "object"
      }
    },
    "securitySchemes": {
      "BasicAuth": {
        "scheme": "basic",
        "type": "http"
      },
      "apiKey": {
        "in": "header",
        "name": "APCA-API-KEY-ID",
        "type": "apiKey"
      },
      "apiSecret": {
        "in": "header",
        "name": "APCA-API-SECRET-KEY",
        "type": "apiKey"
      }
    }
  },
  "info": {
    "contact": {
      "email": "support@alpaca.markets",
      "name": "Alpaca Support",
      "url": "https://alpaca.markets/support"
    },
    "description": "Access real-time and historical market data for US equities, options, crypto, and foreign exchange data through the Alpaca REST and WebSocket APIs. There are APIs for Stock Pricing, Option Pricing, Crypto Pricing, Forex, Logos, Fixed income, Corporate Actions, Screener, and News.\n",
    "license": {
      "name": "Creative Commons Attribution Share Alike 4.0 International",
      "url": "https://spdx.org/licenses/CC-BY-SA-4.0.html"
    },
    "termsOfService": "https://s3.amazonaws.com/files.alpaca.markets/disclosures/library/TermsAndConditions.pdf",
    "title": "Market Data API",
    "version": "1.1"
  },
  "openapi": "3.1.2",
  "paths": {
    "/v1/corporate-actions": {
      "get": {
        "description": "This endpoint provides data about the corporate actions for each given symbol over a specified time period.\n\nBy default (`data_quality=complete`), corporate actions that are still incomplete (for example, missing required fields such as ex-date or CUSIP/ISIN) and have not yet been processed are excluded from the response. Pass `data_quality=all` to also receive those early, incomplete records. Already-processed corporate actions are always returned when `data_quality=complete`, even if they would otherwise be considered incomplete.\n\n> ⚠️ Warning\n>\n> Currently Alpaca has no guarantees on the creation time of corporate actions. There may be delays in receiving corporate actions from our data providers, and there may be delays in processing and making them available via this API. As a result, corporate actions may not be available immediately after they are announced.\n",
        "operationId": "CorporateActions",
        "parameters": [
          {
            "$ref": "#/components/parameters/cas_symbols"
          },
          {
            "$ref": "#/components/parameters/cas_cusips"
          },
          {
            "$ref": "#/components/parameters/cas_types"
          },
          {
            "$ref": "#/components/parameters/cas_region"
          },
          {
            "$ref": "#/components/parameters/cas_start"
          },
          {
            "$ref": "#/components/parameters/cas_end"
          },
          {
            "$ref": "#/components/parameters/cas_ids"
          },
          {
            "$ref": "#/components/parameters/cas_limit"
          },
          {
            "$ref": "#/components/parameters/cas_data_quality"
          },
          {
            "$ref": "#/components/parameters/page_token"
          },
          {
            "$ref": "#/components/parameters/sort"
          }
        ],
        "responses": {
          "200": {
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/corporate_actions_resp"
                }
              }
            },
            "description": "OK",
            "headers": {
              "X-RateLimit-Limit": {
                "$ref": "#/components/headers/ratelimit_limit"
              },
              "X-RateLimit-Remaining": {
                "$ref": "#/components/headers/ratelimit_remaining"
              },
              "X-RateLimit-Reset": {
                "$ref": "#/components/headers/ratelimit_reset"
              }
            }
          },
          "400": {
            "$ref": "#/components/responses/400"
          },
          "401": {
            "$ref": "#/components/responses/401"
          },
          "403": {
            "$ref": "#/components/responses/403"
          },
          "429": {
            "$ref": "#/components/responses/429"
          },
          "500": {
            "$ref": "#/components/responses/500"
          }
        },
        "security": [
          {
            "apiKey": [],
            "apiSecret": []
          },
          {
            "BasicAuth": []
          }
        ],
        "summary": "Corporate actions",
        "tags": [
          "Corporate actions"
        ]
      }
    }
  },
  "servers": [
    {
      "description": "Production",
      "url": "https://data.alpaca.markets"
    },
    {
      "description": "Sandbox",
      "url": "https://data.sandbox.alpaca.markets"
    }
  ],
  "tags": [
    {
      "description": "Corporate actions (splits, dividends, etc.).",
      "name": "Corporate actions"
    }
  ]
}
```