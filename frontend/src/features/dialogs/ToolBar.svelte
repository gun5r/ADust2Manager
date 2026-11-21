<script lang="ts">
  import type { Snippet } from 'svelte'
  import type { AppState } from '../../state/app.svelte'
  import type { ToolRun } from '../../lib/toolRun.svelte'
  import ToolStatus from './ToolStatus.svelte'

  /** The pinned action bar of a tool page, with the window's status right above it: the status takes room from the page, never from the buttons. */
  let { app, tool, children }: { app: AppState; tool: ToolRun; children: Snippet } = $props()
</script>

<ToolStatus {app} {tool} />
<footer class="s-bar">{@render children()}</footer>
