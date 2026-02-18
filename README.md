# Cults3D Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/HallyAus/Cults3D)](https://github.com/HallyAus/Cults3D/releases)
[![License](https://img.shields.io/github/license/HallyAus/Cults3D)](LICENSE)

A Home Assistant custom integration that connects to your [Cults3D](https://cults3d.com) account and provides comprehensive sensors for your creator profile statistics, sales tracking, and the ability to track other creators' popular designs.

## Features

### Profile Statistics
- **Followers Count** - Track how many people are following you
- **Following Count** - See how many creators you're following
- **Creations Count** - Monitor your total number of 3D model uploads

### Sales & Earnings (Your Own Sales)
- **Total Earnings** - Your all-time earnings from sales (EUR)
- **Total Sales** - Number of sales across all time
- **Monthly Earnings** - Earnings from the last 30 days (EUR)
- **Monthly Sales** - Number of sales in the last 30 days

### Featured Creations (Your Own)
- **Latest Creation** - Your most recently published design
- **Top Downloaded (Trending)** - Your most downloaded design

### Tracked Creations (External)
Track any Cults3D creation to monitor its popularity metrics. Useful for:
- Monitoring competitor designs
- Tracking popular models in your niche
- Researching what makes designs successful

**Important:** Sales data for creations you don't own is **NOT available** via the Cults3D API. Tracked creations show public proxy metrics (views, downloads, likes) which correlate with popularity.

All data is fetched efficiently using GraphQL API calls per update cycle (default: every 15 minutes).

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Click on the three dots in the top right corner
3. Select "Custom repositories"
4. Add this repository URL: `https://github.com/HallyAus/Cults3D`
5. Select "Integration" as the category
6. Click "Add"
7. Search for "Cults3D" in HACS and install it
8. Restart Home Assistant

### Manual Installation

1. Download the latest release from the [releases page](https://github.com/HallyAus/Cults3D/releases)
2. Extract the `cults3d` folder to your `custom_components` directory
3. Restart Home Assistant

## Configuration

### Getting Your API Key

1. Log in to your [Cults3D account](https://cults3d.com)
2. Go to **Settings** > **API** (or visit [https://cults3d.com/en/settings/api](https://cults3d.com/en/settings/api))
3. Generate a new API key
4. Copy the API key - you'll need it for the integration setup

### Adding the Integration

1. Go to **Settings** > **Devices & Services** in Home Assistant
2. Click **+ Add Integration**
3. Search for "Cults3D"
4. Enter your Cults3D username (your profile nickname, not email)
5. Enter your API key
6. Click **Submit**

### Tracking External Creations

1. Go to the integration's **Configure** options
2. Select **Add a creation to track**
3. Enter the Cults3D URL or slug of the creation
4. The creation will be tracked on the next update

## Sensors

### Profile Sensors

| Sensor | Description | Unit |
|--------|-------------|------|
| `sensor.cults3d_<username>_followers` | Number of followers | followers |
| `sensor.cults3d_<username>_following` | Number of people you follow | following |
| `sensor.cults3d_<username>_creations` | Total number of creations | creations |

### Sales Sensors (Your Own Sales)

| Sensor | Description | Unit |
|--------|-------------|------|
| `sensor.cults3d_<username>_total_sales_amount` | All-time earnings | EUR |
| `sensor.cults3d_<username>_total_sales_count` | All-time number of sales | sales |
| `sensor.cults3d_<username>_monthly_sales_amount` | Earnings in last 30 days | EUR |
| `sensor.cults3d_<username>_monthly_sales_count` | Sales in last 30 days | sales |

### Creation Sensors (Your Own)

| Sensor | Description | Attributes |
|--------|-------------|------------|
| `sensor.cults3d_<username>_latest_creation` | Most recently published | `url`, `image_url`, `views`, `downloads`, `likes`, `published_at` |
| `sensor.cults3d_<username>_top_downloaded` | Most downloaded (trending) | `url`, `image_url`, `views`, `downloads`, `likes`, `published_at` |

### Tracked Creation Sensors (External)

For each tracked creation, a sensor is created showing downloads count as the primary metric.

| Attribute | Description |
|-----------|-------------|
| `slug` | Creation identifier |
| `name` | Creation name |
| `creator` | Creator's username |
| `url` | Link to creation |
| `views_total` | Total view count |
| `downloads_total` | Total download count |
| `likes_total` | Total like count |
| `published_at` | Publication date |
| `window_start` | Start of 30-day post-release window |
| `window_end` | End of 30-day post-release window |
| `is_within_30_day_window` | Whether currently in first 30 days |

**Note:** All metrics are cumulative totals. The Cults3D API does not provide date-filtered statistics for individual creations. The 30-day window info is calculated from `publishedAt` but metrics cannot be filtered to that period.

## API Limitations

### Sales Data Availability
- **Your own sales:** Available via the `myself` query
- **Other creators' sales:** **NOT available** - this is an API limitation, not a bug

### What We Can Track for External Creations
Since sales data isn't available for creations you don't own, we provide these proxy metrics:
- **Views** - How many times the page was viewed
- **Downloads** - Free and paid downloads combined
- **Likes** - User favorites/likes

These metrics correlate with popularity but are not sales figures.

### 30-Day Post-Release Window
The integration calculates the 30-day window from `publishedAt`:
- `window_start` = `publishedAt`
- `window_end` = `publishedAt + 30 days`

However, the metrics shown are cumulative totals, not filtered to this window, as the API doesn't support date-range queries for creation statistics.

## Example Automations

### Notify on New Sale

```yaml
automation:
  - alias: "Cults3D New Sale Notification"
    trigger:
      - platform: state
        entity_id: sensor.cults3d_username_monthly_sales_count
    condition:
      - condition: template
        value_template: "{{ trigger.to_state.state | int > trigger.from_state.state | int }}"
    action:
      - service: notify.mobile_app
        data:
          title: "New Cults3D Sale!"
          message: "You made a sale! Monthly earnings: €{{ states('sensor.cults3d_username_monthly_sales_amount') }}"
```

### Pre-Built Dashboard

A complete, ready-to-use dashboard YAML is included at `custom_components/cults3d/dashboard/cults3d_dashboard.yaml`.

**To install:**
1. Go to **Settings > Dashboards > Add Dashboard**
2. Choose "New dashboard from scratch"
3. Click the three-dot menu and select **Raw configuration editor**
4. Paste the contents of `cults3d_dashboard.yaml`
5. Replace all instances of `USERNAME` with your Cults3D username (check **Developer Tools > States** and search `cults3d` to find your exact entity IDs)
6. Save

The dashboard includes:
- Profile stats overview with tile cards
- Revenue and growth trend charts (statistics-graph)
- Latest creation and top downloaded cards with images
- Monthly performance summary with calculated averages
- Tracked creations view
- Automation templates for sale notifications, daily reports, and milestone alerts

### Quick Dashboard Card

```yaml
type: vertical-stack
cards:
  - type: entities
    title: Cults3D Profile
    entities:
      - entity: sensor.cults3d_username_followers
        name: Followers
      - entity: sensor.cults3d_username_following
        name: Following
      - entity: sensor.cults3d_username_creations
        name: Creations

  - type: entities
    title: Cults3D Earnings
    entities:
      - entity: sensor.cults3d_username_total_sales_amount
        name: Total Earnings
      - entity: sensor.cults3d_username_total_sales_count
        name: Total Sales
      - entity: sensor.cults3d_username_monthly_sales_amount
        name: Monthly Earnings
      - entity: sensor.cults3d_username_monthly_sales_count
        name: Monthly Sales

  - type: entities
    title: Featured Designs
    entities:
      - entity: sensor.cults3d_username_latest_creation
        name: Latest
      - entity: sensor.cults3d_username_top_downloaded
        name: Trending
```

## Troubleshooting

### Invalid Authentication Error
- Verify your username is your Cults3D **nickname** (shown in your profile URL), not your email
- Ensure your API key is correct and hasn't been regenerated
- Check that your API key has the necessary permissions

### User Not Found
- Make sure you're using your exact Cults3D username (case-sensitive)
- Verify your profile is public and accessible

### Sales Data Shows Zero
- Sales data requires the `myself` GraphQL query which needs proper API authentication
- Check the Home Assistant logs for any authentication warnings

### Rate Limiting
The integration polls every 15 minutes by default. Cults3D enforces ~60 requests/30 seconds and ~500 requests/day.

## GraphQL Schema Notes

This integration queries the Cults3D GraphQL API at `https://cults3d.com/graphql`. The queries are defined in `coordinator.py`:

**Available fields on User:**
- `nick`, `followersCount`, `followeesCount`, `creationsCount`

**Available fields on Creation:**
- `name`, `shortUrl`, `viewsCount`, `downloadsCount`, `likesCount`, `illustrationImageUrl`, `publishedAt`

**Valid sort enums:**
- `BY_PUBLICATION`, `BY_DOWNLOADS`

**Money type:**
- `income { value }` - returns numeric value in EUR

**Note:** `BY_VIEWS`, `BY_SALES` sorts and `salesCount`/`totalCount` fields are NOT available in the current schema.

## Support the Project

If you find this integration useful, consider buying me a coffee!

<a href="https://buymeacoffee.com/printforge" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" ></a>

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This integration is not officially affiliated with or endorsed by Cults3D. Use at your own risk.
