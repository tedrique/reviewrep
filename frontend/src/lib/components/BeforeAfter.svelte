<section class="py-20 px-4">
	<div class="max-w-4xl mx-auto">
		<div class="grid md:grid-cols-2 gap-5">
			<div class="scroll-reveal bg-gradient-to-br from-rose-500/10 to-rose-500/5 rounded-2xl p-8 border border-rose-500/10">
				<div class="text-xs font-bold text-rose-400 uppercase tracking-widest mb-5">Without ReviewRep</div>
				<ul class="space-y-3 text-sm text-white/50">
					{#each [
						'Negative reviews sit unanswered for days',
						'Google ranks you lower than competitors who reply',
						'Customers see silence and choose someone else',
						'You spend hours writing replies or just give up',
						'Unhappy customers never come back'
					] as item}
						<li class="flex items-start gap-2"><span class="text-rose-400/60 mt-0.5">&#10007;</span> {item}</li>
					{/each}
				</ul>
			</div>
			<div class="scroll-reveal scroll-reveal-delay-1 bg-gradient-to-br from-emerald-500/10 to-emerald-500/5 rounded-2xl p-8 border border-emerald-500/10">
				<div class="text-xs font-bold text-emerald-400 uppercase tracking-widest mb-5">With ReviewRep</div>
				<ul class="space-y-3 text-sm text-white/50">
					{#each [
						'Every review gets a professional reply in seconds',
						'Google sees engagement — boosts your ranking',
						'Customers see you care — trust and loyalty',
						'10 seconds to approve instead of 10 minutes',
						'Unhappy customers get heard — many come back'
					] as item}
						<li class="flex items-start gap-2"><span class="text-emerald-400 mt-0.5">&#10003;</span> {item}</li>
					{/each}
				</ul>
			</div>
		</div>

		<!-- ROI callout -->
		<div class="scroll-reveal scroll-reveal-delay-2 mt-8 text-center bg-gradient-to-r from-blue-500/10 via-violet-500/10 to-blue-500/10 rounded-2xl p-8 border border-blue-500/10">
			<p class="text-white/50 mb-2">One new customer per month from better reviews</p>
			<p class="text-3xl md:text-4xl font-black bg-gradient-to-r from-blue-400 to-violet-400 bg-clip-text text-transparent">= £200-500+ revenue</p>
			<p class="text-white/30 text-sm mt-2">Your subscription pays for itself with a single extra booking.</p>
		</div>
	</div>
</section>
