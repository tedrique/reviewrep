<section id="pricing" class="py-20 md:py-28 px-4">
	<div class="max-w-4xl mx-auto">
		<div class="scroll-reveal text-center mb-14">
			<h2 class="text-2xl md:text-4xl font-bold mb-3">Simple, honest pricing</h2>
			<p class="text-white/40">Start free for 7 days. No credit card needed.</p>
		</div>

		<div class="grid md:grid-cols-2 gap-6 max-w-3xl mx-auto">
			<!-- Starter -->
			<div class="scroll-reveal scroll-reveal-delay-1 bg-white/[0.03] border border-white/5 rounded-2xl p-8 hover:border-white/10 transition-all duration-300">
				<h3 class="text-xl font-bold mb-2">Starter</h3>
				<div class="flex items-baseline gap-1 mb-1">
					<span class="text-4xl md:text-5xl font-black">£19</span>
					<span class="text-white/30">/mo</span>
				</div>
				<p class="text-white/30 text-sm mb-8">For a single location</p>
				<ul class="space-y-3 text-sm text-white/50 mb-8">
					{#each ['Up to 50 AI responses/month', '1 business location', 'Tone customisation', 'One-click approve', 'British English'] as item}
						<li class="flex items-center gap-2"><span class="text-emerald-400">&#10003;</span> {item}</li>
					{/each}
				</ul>
				<a href="/login" class="block text-center py-3.5 rounded-xl border border-white/10 text-white/70 hover:bg-white/5 hover:text-white transition-all font-medium">Start Free Trial</a>
			</div>

			<!-- Pro -->
			<div class="scroll-reveal scroll-reveal-delay-2 relative bg-gradient-to-br from-blue-500/10 to-violet-500/10 border border-blue-500/20 rounded-2xl p-8 hover:border-blue-500/30 transition-all duration-300 shadow-lg shadow-blue-500/5">
				<div class="absolute -top-3 left-1/2 -translate-x-1/2 bg-gradient-to-r from-blue-500 to-violet-500 text-xs font-bold px-4 py-1 rounded-full">Most Popular</div>
				<h3 class="text-xl font-bold mb-2">Pro</h3>
				<div class="flex items-baseline gap-1 mb-1">
					<span class="text-4xl md:text-5xl font-black">£39</span>
					<span class="text-white/30">/mo</span>
				</div>
				<p class="text-white/30 text-sm mb-8">For growing businesses</p>
				<ul class="space-y-3 text-sm text-white/50 mb-8">
					{#each ['Unlimited AI responses', 'Up to 3 locations', 'Advanced tone settings', 'Priority support', 'Response analytics', 'Everything in Starter'] as item}
						<li class="flex items-center gap-2"><span class="text-emerald-400">&#10003;</span> {item}</li>
					{/each}
				</ul>
				<a href="/login" class="block text-center py-3.5 rounded-xl bg-gradient-to-r from-blue-500 to-violet-500 font-semibold hover:opacity-90 transition-all hover:shadow-lg hover:shadow-blue-500/20">Start Free Trial</a>
			</div>
		</div>
	</div>
</section>
