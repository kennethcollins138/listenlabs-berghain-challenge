import requests
import math

class GameController:
    def __init__(self, config: dict = dict()):
        # need config for model conf/
        self.config: dict = config
        
        # available after starting game
        self.game_uuid: str = ""
        self.constraints = {}
        self.attribute_statistics = {}
        
        # Game state
        self.N = 1000  # venue capacity
        self.accepted_counts = {}
        self.remaining_required = {}
        self.R = self.N  # remaining slots
        self.rejects = 0
        self.MAX_REJECTS = 20000
        
        # Computed probabilities
        self.p_a = {}  # marginal probabilities
        self.P11 = {}  # pairwise joint probabilities P(A=1,B=1)
        
    def start(self, config: dict):
        """
        start game makes the request to start the game
        """
        # Added https:// to the URL
        r = requests.get("https://berghain.challenges.listenlabs.ai/new-game?scenario=1&playerId=9c9b165c-3a48-489a-b25e-8fa2621a4ea2")
            
        if r.status_code != 200:
            print("failed to start game")
            return
        
        # Added error handling for JSON parsing
        try:
            game_data = r.json()
        except requests.exceptions.JSONDecodeError:
            print("Failed to parse response as JSON")
            return
            
        self.game_uuid = game_data["gameId"]
        print(f"Game started: {self.game_uuid}")
        
        # Store constraints and statistics
        self.constraints = game_data["constraints"]
        self.attribute_statistics = game_data["attributeStatistics"]
        
        # Initialize game state
        self._initialize_probabilities()
        self._initialize_game_state()
        
    def _initialize_probabilities(self):
        """Compute marginal probabilities and pairwise joint probabilities"""
        self.p_a = self.attribute_statistics["relativeFrequencies"]
        correlations = self.attribute_statistics["correlations"]
        
        # Compute pairwise joint probabilities P(A=1,B=1) from correlations
        self.P11 = {}
        attrs = list(self.p_a.keys())
        
        for a in attrs:
            self.P11[a] = {}
            for b in attrs:
                if a == b:
                    self.P11[a][b] = self.p_a[a]
                else:
                    # P11 = ρ_ab * sqrt(p_a(1-p_a)p_b(1-p_b)) + p_a * p_b
                    rho = correlations[a][b]
                    p_a_val = self.p_a[a]
                    p_b_val = self.p_a[b]
                    
                    self.P11[a][b] = (rho * math.sqrt(p_a_val * (1 - p_a_val) * p_b_val * (1 - p_b_val)) + 
                                     p_a_val * p_b_val)
    
    def _initialize_game_state(self):
        """Initialize counters and requirements based on constraints"""
        attrs = list(self.p_a.keys())
        self.accepted_counts = {a: 0 for a in attrs}
        
        # Convert constraints to remaining required counts
        self.remaining_required = {}
        for constraint in self.constraints:
            attr = constraint["attribute"]
            min_count = constraint["minCount"]
            self.remaining_required[attr] = min_count
    
    def _compute_expected_future_supply(self):
        """Compute expected future supply for each attribute"""
        return {a: self.R * self.p_a[a] for a in self.p_a.keys()}
    
    def _compute_alphas(self):
        """Compute dynamic weights for scoring"""
        alphas = {}
        for a in self.p_a.keys():
            remaining_req = max(0, self.remaining_required[a] - self.accepted_counts[a])
            alphas[a] = remaining_req / (self.R + 1e-9)
        return alphas
    
    def _should_force_accept(self, person_attributes, expected_future):
        """Check if we must accept this person to meet constraints"""
        for attr in person_attributes:
            if attr in person_attributes and person_attributes[attr]:
                remaining_req = max(0, self.remaining_required[attr] - self.accepted_counts[attr])
                if expected_future[attr] < remaining_req:
                    return True
        return False
    
    def _compute_score(self, person_attributes):
        """Compute score for this person based on current needs"""
        alphas = self._compute_alphas()
        score = 0
        for attr, has_attr in person_attributes.items():
            if has_attr and attr in alphas:
                score += alphas[attr]
        return score
    
    def make_decision(self, person_data):
        """
        Make accept/reject decision for a person
        Returns: True to accept, False to reject
        """
        person_attributes = person_data["attributes"]
        
        # Compute expected future supply
        expected_future = self._compute_expected_future_supply()
        
        # Forced accept check
        if self._should_force_accept(person_attributes, expected_future):
            return True
        
        # Scoring rule
        score = self._compute_score(person_attributes)
        
        # Accept if score is positive and we have capacity
        return score > 0 and self.R > 0
    
    def update_state(self, accepted, person_attributes):
        """Update game state after decision"""
        if accepted:
            self.R -= 1
            for attr, has_attr in person_attributes.items():
                if has_attr and attr in self.accepted_counts:
                    self.accepted_counts[attr] += 1
        else:
            self.rejects += 1
    
    def get_next_person_and_decide(self, person_index, accept=None):
        """Get next person and optionally make decision on previous person"""
        url = f"https://berghain.challenges.listenlabs.ai/decide-and-next?gameId={self.game_uuid}&personIndex={person_index}"
        
        if accept is not None:
            url += f"&accept={str(accept).lower()}"
        
        try:
            r = requests.get(url)
            if r.status_code != 200:
                print(f"Request failed with status {r.status_code}")
                return None
            
            return r.json()
        except requests.exceptions.JSONDecodeError:
            print("Failed to parse response as JSON")
            return None
    
    def run_game(self):
        """Run the complete game using the online algorithm"""
        person_index = 0
        
        # Get first person without decision (personIndex=0, no accept param)
        response = self.get_next_person_and_decide(person_index)
        if not response or response["status"] != "running":
            print(f"Failed to start game properly: {response}")
            return response
        
        while response and response["status"] == "running" and self.R > 0 and self.rejects < self.MAX_REJECTS:
            # Get current person data
            person_data = response["nextPerson"]
            person_index = person_data["personIndex"]
            
            # Make decision on this person
            should_accept = self.make_decision(person_data)
            self.update_state(should_accept, person_data["attributes"])
            
            print(f"Person {person_index}: {'ACCEPT' if should_accept else 'REJECT'} - {person_data['attributes']}")
            
            # Make the decision and get next person
            response = self.get_next_person_and_decide(person_index, should_accept)
            
            if not response:
                print("No response received")
                break
            
            # Print progress occasionally
            if person_index % 100 == 0:
                print(f"Progress - Accepted: {self.N - self.R}, Rejected: {self.rejects}")
                print(f"Current counts: {self.accepted_counts}")
                print(f"Remaining required: {self.remaining_required}")
        
        # Game ended
        if response:
            print(f"Game ended with status: {response['status']}")
            if response["status"] == "completed":
                print(f"Successfully filled venue! Total rejections: {response.get('rejectedCount', self.rejects)}")
            elif response["status"] == "failed":
                print(f"Game failed: {response.get('reason', 'Unknown reason')}")
        
        return response
